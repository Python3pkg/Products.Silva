# -*- coding: iso-8859-1 -*-
# Copyright (c) 2002-2004 Infrae. All rights reserved.
# See also LICENSE.txt
# $Id: Image.py,v 1.55 2004/09/30 08:20:57 jw Exp $

# Python
import re, string
from cStringIO import StringIO
from types import StringType, IntType
from zipfile import ZipFile
from cgi import escape

# Zope
import OFS
from AccessControl import ClassSecurityInfo
from Globals import InitializeClass
from Products.PageTemplates.PageTemplateFile import PageTemplateFile
from DateTime import DateTime
from webdav.WriteLockInterface import WriteLockInterface

# Silva
import SilvaPermissions
from Asset import Asset
from Products.Silva import mangle
from Products.Silva import upgrade
# misc
from helpers import add_and_edit

try:
    import PIL.Image
    havePIL = 1
except ImportError:
    havePIL = 0

try:
    from Products.ExtFile.ExtImage import ExtImage
except ImportError:  
    pass

from interfaces import IAsset, IUpgrader

icon = "www/silvaimage.gif"
addable_priority = -0.4

class Image(Asset):
    """Web graphics (gif, jpg, png) can be uploaded and inserted in 
       documents, or used as viewable assets.
    """    
    security = ClassSecurityInfo()

    meta_type = "Silva Image"

    __implements__ = (WriteLockInterface, IAsset)
    
    re_WidthXHeight = re.compile(r'^([0-9]+|\*)[Xx]([0-9\*]+|\*)$')
    re_percentage = re.compile(r'^([0-9\.]+)\%$')
    re_box = re.compile(r'^([0-9]+)[Xx]([0-9]+)-([0-9]+)[Xx]([0-9]+)')
    
    thumbnail_size = 120

    hires_image = None
    thumbnail_image = None
    web_scale = '100%'
    web_format = 'JPEG'
    web_formats = ('JPEG', 'GIF', 'PNG')
    web_crop = ''

    _web2ct = {
        'JPEG': 'image/jpeg',
        'GIF': 'image/gif',
        'PNG': 'image/png',
    }

    def __init__(self, id, title):
        Image.inheritedAttribute('__init__')(self, id, title)
        self.image = None # should create default 
        
    security.declareProtected(SilvaPermissions.AccessContentsInformation,
                              'image')
    
    security.declareProtected(SilvaPermissions.View, 'index_html')
    def index_html(self, view_method=None, REQUEST=None):
        """view image data
        
        view_method: parameter is set by preview_html (for instance) but
            ignored here.
        """
        img = None
        if REQUEST is None:
            REQUEST = self.REQUEST
        RESPONSE = REQUEST.RESPONSE
        query = REQUEST.QUERY_STRING
        if query == 'hires':
            img = self.hires_image
        elif query == 'thumbnail':
            img = self.thumbnail_image
        if img is None:
            img = self.image
        return self._image_index_html(img, REQUEST, RESPONSE)

    def manage_afterAdd(self, item, container):
        for id in ('hires_image', 'image', 'thumbnail_image'):
            img = getattr(self, id, None)
            if img is None:
                continue
            # fake it, to get filename correct
            img.id = self.id
            img.manage_afterAdd(img, self)
            img.id = id
        return Image.inheritedAttribute('manage_afterAdd')(self, item,
            container)

    def manage_beforeDelete(self, item, container):
        """explicitly remove the images"""
        for id in ('hires_image', 'image', 'thumbnail_image'):
            self._remove_image(id, set_none=0)
        return Image.inheritedAttribute('manage_beforeDelete')(self, item,
            container)

    def manage_afterClone(self, item):
        "copy support"
        for id in ('image', 'hires_image', 'thumbnail_image'):
            img = getattr(self, id, None)
            if img is None:
                continue
            # fake it, to get filename correct
            img.id = self.id
            img.manage_afterClone(item)
            img.id = id
        return Image.inheritedAttribute('manage_afterClone')(self, item)
        
    security.declareProtected(SilvaPermissions.ChangeSilvaContent,
                              'set_title')
    def set_title(self, title):
        """Set the title of the silva object.
        Overrides SilvaObject set_title() to accomodate the OFS.Image.Image 
        title attribute - which in turn is used in the tag() method.
        """
        self._title = title # legacy I guess
        Image.inheritedAttribute('set_title')(self, title)
        if self.image:
            self.image.title = self.get_title()

    def set_web_presentation_properties(self, web_format, web_scale, web_crop):
        """sets format and scaling for web presentation

            web_format (str): either JPEG or PNG (or whatever other format 
                makes sense, must be recognised by PIL)
            web_scale (str): WidthXHeight or nn.n%
            web_crop (str): X1xY1-X2xY2, crop-box or empty for no cropping

            raises ValueError if web_scale cannot be parsed.

            automaticaly updates cached web presentation image
            
        """
        update_cache = 0
        if self.hires_image is None:
            update_cache = 1
            self.hires_image = self.image
            self.image = None
        if self.web_format != web_format:
            self.web_format = web_format
            update_cache = 1
        # check if web_scale can be parsed:
        canonical_scale = self.getCanonicalWebScale(web_scale)
        if self.web_scale != web_scale:
            update_cache = 1
            self.web_scale = web_scale
        # check if web_crop can be parsed:
        cropbox = self.getCropBox(web_crop)
        if self.web_crop != web_crop:
            update_cache = 1
            self.web_crop = web_crop
        if self.hires_image is not None and update_cache:
            self._createDerivedImages()
   
    security.declareProtected(SilvaPermissions.ChangeSilvaContent,
                              'set_image')
    def set_image(self, file):
        """Set the image object.
        """
        if self.hires_image is not None:
            self.hires_image.manage_beforeDelete(self.hires_image, self)
        try:
            ct = file.headers.get('Content-Type')
        except AttributeError:
            ct = None
        self._image_factory('hires_image', file, ct)
        self._set_redirect(self.hires_image)
        format = self.getFormat()
        if format in self.web_formats:
            self.web_format = format
        self._createDerivedImages()

    security.declareProtected(SilvaPermissions.ChangeSilvaContent,
                              'set_zope_image')
    def set_zope_image(self, zope_img):
        """Set the image object with zope image.
        """
        self.hires_image = zope_img
        self._createDerivedImages()

    security.declareProtected(SilvaPermissions.View, 'getCanonicalWebScale')
    def getCanonicalWebScale(self, scale=None):
        """returns (width, height) of web image"""
        if scale is None:
            scale = self.web_scale
        m = self.re_WidthXHeight.match(scale)
        if m is None:
            m = self.re_percentage.match(scale)
            if m is None:
                raise ValueError, ("'%s' is not a valid scale identifier. "
                    "Probably a percent symbol is missing.") % (scale, )
            cropbox = self.getCropBox()
            if cropbox:
                x1, y1, x2, y2 = cropbox
                width = x2 - x1
                height = y2 - y1
            else:
                width, height = self.getDimensions()
            percentage = float(m.group(1))/100.0
            width = int(width * percentage)
            height = int(height * percentage)
        else:
            img_w, img_h = self.getDimensions()
            width = m.group(1)
            height = m.group(2)
            if width == height == '*':
                raise ValueError, ("'%s' is not a valid scale identifier. "
                    "At least one number is required.") % (scale, )
            if width == '*':
                height = int(height)
                width = img_w * height / img_h
            elif height == '*':
                width = int(width)
                height = img_h * width / img_w
            else:
                width = int(width)
                height = int(height)
        return width, height

    security.declareProtected(SilvaPermissions.View, 'getCropBox')
    def getCropBox(self, crop=None):
        """return crop box"""
        if crop is None:
            crop = self.web_crop
        crop = crop.strip()
        if crop == '':
            return None
        m = self.re_box.match(crop)
        if m is None:
            raise ValueError, "'%s' is not a valid crop identifier" % (crop, )
        x1 = int(m.group(1))
        y1 = int(m.group(2))
        x2 = int(m.group(3))
        y2 = int(m.group(4))
        if x1 > x2 and y1 > y2:
            s = x1
            x1 = x2
            x2 = s
            s = y1
            y1 = y2
            y2 = s
        cropbox = (x1, y1, x2, y2)
        image = self._getPILImage(self.hires_image)
        bbox = image.getbbox()
        if x1 < bbox[0]:
            x1 = bbox[0]
        if y1 < bbox[1]:
            y1 = bbox[1]
        if x2 > bbox[2]:
            x2 = bbox[2]
        if y2 > bbox[3]:
            y2 = bbox[3]
        if x1 >= x2 or y1 >= y2:
            raise ValueError, "'%s' defines an impossible cropping" % (crop, )
        return (x1, y1, x2, y2)

    security.declareProtected(SilvaPermissions.View, 'getDimensions')
    def getDimensions(self, img=None):
        """returns width, heigt of (hi res) image
        
            raises ValueError if there is no way of determining the dimenstions
            return 0, 0 if there is no image
            returns width, height otherwise
        
        """
        if img is None:
            img = self.hires_image
        if img is None:
            img = self.image
        if img is None:
            return (0, 0)
        width, height = img.width, img.height
        if img.meta_type == 'ExtImage':
            width = width()
            height = height()
            if (width, height) == (0, 0):
                width = height = None
        if not (isinstance(width, IntType) and isinstance(height, IntType)):
            width, height = self._get_dimensions_from_image_data(img)
            if img.meta_type == 'Image':
                img.width = width
                img.height = height
        return width, height

    security.declareProtected(SilvaPermissions.View, 'getFormat')
    def getFormat(self):
        """returns image format (PIL identifier) or unknown if there is no PIL
        """
        try:
            return self._getPILImage(self.hires_image).format
        except ValueError:
            return 'unknown'

    security.declareProtected(SilvaPermissions.View, 'getImage')
    def getImage(self, hires=1, webformat=0, REQUEST=None):
        """return image"""
        if hires and not webformat:
            image = self.hires_image
        elif not hires and webformat:
            image = self.image
        elif hires and webformat:
            pil_image = self._getPILImage(self.hires_image)
            pil_image = self._prepareWebFormat(pil_image)
            image_data = StringIO()
            pil_image.save(image_data, self.web_format)
            del(pil_image)
            image = OFS.Image.Image(
                'custom_image', self.get_title(), image_data)
        elif not hires and not webformat:
            raise ValueError, "Low resolution image in original format is " \
                "not supported"
        if REQUEST is not None:
            return self._image_index_html(image, REQUEST, REQUEST.RESPONSE)
        else:
            return self._get_image_data(image).read()
        
    security.declareProtected(SilvaPermissions.View, 'tag')
    def tag(self, hires=0, thumbnail=0, **kw):
        """ return xhtml tag
        
        Since 'class' is a Python reserved word, it cannot be passed in
        directly in keyword arguments which is a problem if you are
        trying to use 'tag()' to include a CSS class. The tag() method
        will accept a 'css_class' argument that will be converted to
        'class' in the output tag to work around this.
        """
        image, img_src = self._get_image_and_src(hires, thumbnail)
        title = self.get_title()
        width, height = self.getDimensions(image)
        named = []
        
        if kw.has_key('css_class'):
            kw['class'] = kw['css_class']
            del kw['css_class']
            
        for name, value in kw.items():
            named.append('%s="%s"' % (escape(name), escape(value)))
        named = ' '.join(named)
        return '<img src="%s" width="%s" height="%s" alt="%s" %s />' % (
            img_src, width, height, escape(title), named)
            
    security.declareProtected(SilvaPermissions.View, 'tag')
    def url(self, hires=0, thumbnail=0):
        "return url of image"
        image, img_src = self._get_image_and_src(hires, thumbnail)
        return img_src

    security.declareProtected(SilvaPermissions.View, 'getWebFormat')
    def getWebFormat(self):
        """Return file format of web presentation image
        """
        try:
            return self._getPILImage(self.image).format
        except ValueError:
            return 'unknown'

    security.declareProtected(SilvaPermissions.View, 'getWebScale')
    def getWebScale(self):
        """Return scale percentage / WxH of web presentation image
        """
        return '%s' % self.web_scale

    security.declareProtected(SilvaPermissions.View, 'getWebCrop')
    def getWebCrop(self):
        """Return crop identifier
        """
        return '%s' % self.web_crop

    security.declareProtected(SilvaPermissions.View, 'canScale')
    def canScale(self):
        """returns if scaling/converting is possible"""
        return havePIL
    
    security.declareProtected(SilvaPermissions.ChangeSilvaContent,
        'getFileSystemPath')
    def getFileSystemPath(self):
        """return path on filesystem for containing image"""
        image = self.hires_image
        if image.meta_type == 'ExtImage':
            return image.get_filename()
        return None

    security.declareProtected(SilvaPermissions.View, 'getOrientation')
    def getOrientation(self):
        """ returns Image orientation (string) """
        width, height = self.getDimensions()
        if width == height:
            return "square"
        elif width > height:
            return "landscape"
        return "portrait"

    def manage_FTPget(self, *args, **kwargs):
        return self.image.manage_FTPget(*args, **kwargs)

    def content_type(self):
        return self.image.content_type

    def PUT(self, REQUEST, RESPONSE):
        """Handle HTTP PUT requests"""
        return self.image.PUT(REQUEST, RESPONSE)

    def HEAD(self, REQUEST, RESPONSE):
        """ forward the request to the underlying image object
        """
        # XXX: copy & paste from "index_html"
        img = None
        query = REQUEST.QUERY_STRING
        if query == 'hires':
            img = self.hires_image
        elif query == 'thumbnail':
            img = self.thumbnail_image
        if img is None:
            img = self.image
        return img.HEAD(REQUEST, RESPONSE)

    def get_file_size(self):
        return self.hires_image.get_size()
    
    security.declareProtected(SilvaPermissions.View, 'get_scaled_file_size')
    def get_scaled_file_size(self):
        return self.image.get_size()

    ##########
    ## private

    def _getPILImage(self, img):
        """return PIL of an image

            raise ValueError if no PIL is available
            raise ValueError if image could not be identified
        """
        if not havePIL:
            raise ValueError, "No PIL installed."""
        if img is None:
            img = self.image
        image_reference = self._get_image_data(img)
        try:
            image = PIL.Image.open(image_reference)
        except IOError, e:
            raise ValueError, e
        return image

    def _createDerivedImages(self):
        self._createWebPresentation()
        self._createThumbnail()

    def _createWebPresentation(self):
        width, height = self.getCanonicalWebScale()
        cropbox = self.getCropBox()
        try:
            image = self._getPILImage(self.hires_image)
        except ValueError:
            # XXX: warn the user, no scaling or converting has happend
            self.image = self.hires_image
            return
        if (self.web_scale == '100%' and image.format == self.web_format and
                not self.web_crop):
            # there image is neither scaled nor changed in format, just use
            # the same one
            if self.image is not None and not self._image_is_hires():
                self._remove_image('image')
            self.image = self.hires_image
            return
        else:
            if self.image is not None and self._image_is_hires():
                self.image = None
        web_image_data = StringIO()
        if cropbox:
            image = image.crop(cropbox)
        if self.web_scale != '100%':
            image = image.resize((width, height), PIL.Image.ANTIALIAS)
        image = self._prepareWebFormat(image)
        image.save(web_image_data, self.web_format)
        ct = self._web2ct[self.web_format]
        self._image_factory('image', web_image_data, ct)
        self._set_redirect(self.image)

    def _createThumbnail(self):
        try:
            image = self._getPILImage(self.hires_image)
        except ValueError:
            # no thumbnail
            self.thumbnail_image = None
            return
        thumb = image.copy()
        ts = self.thumbnail_size
        thumb.thumbnail((ts, ts), PIL.Image.ANTIALIAS)
        thumb = self._prepareWebFormat(thumb)
        thumb_data = StringIO()
        thumb.save(thumb_data, self.web_format)
        ct = self._web2ct[self.web_format]
        self._image_factory('thumbnail_image', thumb_data, ct)

    def _prepareWebFormat(self, pil_image):
        """converts image's mode if necessary"""

        if pil_image.mode != 'RGB' and self.web_format == 'JPEG':
            pil_image = pil_image.convert("RGB")
        return pil_image

    def _image_factory(self, id, file, content_type):
        repository = self._useFSStorage()
        image = getattr(self, id, None)
        created = 0
        title = self.get_title()
        if repository is None:
            image = OFS.Image.Image(id, title, file,
                content_type=content_type)
            created = 1
        else:
            if image is not None and image.meta_type != 'ExtImage':
                self._remove_image(id)
                image = None
            if image is None:
                image = ExtImage(self.getId(), title)
                created = 1
                image._repository = repository
                image = image.__of__(self)
            # self.getId() is used to get a `normal' file name. We restore
            # it later to get the a working absolute_url()
            image.id = self.getId()
            file.seek(0)
            # ensure consistent mimetype assignment by deleting content-type header
            fix_content_type_header(file)
            image.manage_file_upload(file, content_type=content_type)
            image = image.aq_base
            # set the actual id (so that absolute_url works)
            image.id = id
        # assert we "know" the image type and can do something with it:
        self.getDimensions(image)
        if created:
            old_img = getattr(self, id, None)
            if old_img is not None:
                old_img.manage_beforeDelete(image, self)
        setattr(self, id, image)
        if created:
            image.manage_afterAdd(image, self)
        return image
    
    def _useFSStorage(self):
        """return true if we should store images on the filesystem"""
        service_files = getattr(self, 'service_files', None)
        assert service_files is not None, "There is no service_files. " \
            "Refresh your silva root."
        if service_files.useFSStorage():
            return service_files.cookPath(service_files.filesystem_path())
        return None

    def _get_image_and_src(self, hires=0, thumbnail=0):
        img_src = self.absolute_url()
        if hires:
            image = self.hires_image
            img_src += '?hires'
        elif thumbnail:
            image = self.thumbnail_image
            img_src += '?thumbnail'
        else:
            image = self.image
        if self._is_static_mode(image):
            # apache rewrite in effect
            img_src = image.static_url()
        return image, img_src

    def _is_static_mode(self, image):
        if image.meta_type == 'Image':
            return 0
        assert image.meta_type == 'ExtImage'
        return image.static_mode()

    def _set_redirect(self, image, to=1):
        if image.meta_type == 'ExtImage':
            image.redirect_default_view = to

    def _remove_image(self, id, set_none=1):
        image = getattr(self, id, None)
        if image is None:
            return
        image.manage_beforeDelete(self.image, self)
        if set_none:
            setattr(self, id, None)

    def _image_is_hires(self):
        return (self.image is not None and
            self.image.aq_base is self.hires_image.aq_base)

    def _get_dimensions_from_image_data(self, img):
        """return width, heigth computed from image's data

            raises ValueError if the dimensions could not be determined
        """
        if havePIL:
            pil_image = self._getPILImage(img)
            w, h = pil_image.size
        else:
            data_handle = self._get_image_data(img)
            data = data_handle.read()
            data_handle.close()
            ct, w, h = OFS.Image.getImageInfo(data)
            if w <= 0 or h <= 0:
                raise ValueError, "Could not identify image type."
        return w, h

    def _get_image_data(self, img):
        """return file like object of image's data"""
        if img.meta_type == 'Image': #OFS.Image.Image
            image_reference = StringIO(str(img.data))
        else:
            image_reference = img._get_fsname(img.get_filename())
            image_reference = open(image_reference, 'rb')
        return image_reference

    def _image_index_html(self, image, REQUEST, RESPONSE):
        args = ()
        kw = {}
        if image.meta_type == 'Image':
            # ExtFile and OFS.Image have different signature
            args = (REQUEST, RESPONSE)
        else:
            kw['REQUEST'] = REQUEST
        return image.index_html(*args, **kw)


InitializeClass(Image)
    
manage_addImageForm = PageTemplateFile(
    "www/imageAdd", globals(), __name__='manage_addImageForm')

# FIXME: Image and File Assets should be refactored - they share quite
# some functionality which can be generalized.
#
# Copy code from ExtFile, but we don't want a dependency per se:
bad_chars =  r""" ,;()[]{}~`'"!@#$%^&*+=|\/<>?���������������������������������������������������������ݟ����"""
good_chars = r"""_____________________________AAAAAAaaaaaaCcEEEEEeeeeeIIIIiiiiNnOOOOOOooooooSssUUUUuuuuYYyyZz"""
TRANSMAP = string.maketrans(bad_chars, good_chars)

def manage_addImage(context, id, title, file=None, REQUEST=None):
    """Add an Image."""
    id = mangle.Id(context, id, file=file, interface=IAsset)
    id.cook()
    if not id.isValid():
        return
    id = str(id)
    img = Image(id, title)
    context._setObject(id, img)
    img = getattr(context, id)
    if file:
        img.set_image(file)
    img.set_title(title)

    add_and_edit(context, id, REQUEST)
    return img

class ImageStorageConverter:

    __implements__ = IUpgrader

    def upgrade(self, asset):
        assert asset.meta_type == 'Silva Image'
        self._restore_image(asset, 'hires_image')
        asset._createDerivedImages()
        return asset

    def _restore_image(self, asset, id):
        image = getattr(asset, id, None)
        if image is None:
            return
        if image.meta_type == 'Image':
            data = StringIO(str(image.data))
        elif image.meta_type == 'ExtImage':
            data = open(image.get_fsname(), 'rb')
        else:
            raise RuntimeError, "Invalid asset at %s" % asset.absolute_url()
        ct = image.getContentType()
        asset._image_factory(id, data, ct)

# Register Image factory for image mimetypes
import mimetypes
from Products.Silva import assetregistry

mt = mimetypes.types_map.values()
mt  = [mt for mt in mt if mt.startswith('image')]
assetregistry.registerFactoryForMimetypes(mt, manage_addImage, 'Silva')
