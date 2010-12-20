# -*- coding: utf-8 -*-
# Copyright (c) 2002-2010 Infrae. All rights reserved.
# See also LICENSE.txt
# $Id$

# Python
import re
import os
import logging
from cStringIO import StringIO
from cgi import escape

logger = logging.getLogger('silva.image')

# Zope 3
from five import grok
from zope import component, schema
from zope.i18n import translate
from zope.interface import Interface
import zope.app.container.interfaces

# Zope 2
from AccessControl import ClassSecurityInfo
from App.class_init import InitializeClass
import OFS.interfaces
import transaction

# Silva
from Products.Silva import mangle, SilvaPermissions
from Products.Silva.Asset import Asset

from silva.core import conf as silvaconf
from silva.core import interfaces
from silva.core.conf import schema as silvaschema
from silva.core.views import z3cforms as silvaz3cforms
from silva.core.views.traverser import SilvaPublishTraverse
from silva.translations import translate as _
from z3c.form import field

try:
    import PIL.Image
    havePIL = 1
except ImportError:
    havePIL = 0


def manage_addImage(context, id, title, file=None, REQUEST=None):
    """Add an Image.
    """
    image_obj = image_factory(context, id, None, file)
    if image_obj is None:
        return None
    id = image_obj.id
    context._setObject(id, image_obj)
    image_obj = getattr(context, id)
    if file:
        try:
            image_obj.set_image(file)
        except ValueError:
            # uploaded contents is not a proper image file
            transaction.abort()
            raise
    image_obj.set_title(title)
    return image_obj


class Image(Asset):
    __doc__ = _("""Web graphics (gif, jpg, png) can be uploaded and inserted in
       documents, or used as viewable assets.
    """)
    security = ClassSecurityInfo()

    meta_type = "Silva Image"

    grok.implements(interfaces.IImage)

    re_WidthXHeight = re.compile(r'^([0-9]+|\*)[Xx]([0-9\*]+|\*)$')
    re_percentage = re.compile(r'^([0-9\.]+)\%$')
    re_box = re.compile(r'^([0-9]+)[Xx]([0-9]+)-([0-9]+)[Xx]([0-9]+)')

    thumbnail_size = 120

    image = None
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

    silvaconf.priority(-3)
    silvaconf.icon('www/silvaimage.gif')
    silvaconf.factory('manage_addImage')


    def set_web_presentation_properties(self, web_format, web_scale, web_crop):
        """Sets format and scaling for web presentation.

        web_format (str): either JPEG or PNG (or whatever other format
        makes sense, must be recognised by PIL).
        web_scale (str): WidthXHeight or nn.n%.
        web_crop (str): X1xY1-X2xY2, crop-box or empty for no cropping.

        Raises ValueError if web_scale cannot be parsed.

        Automaticaly updates cached web presentation image.
        """
        update_cache = 0
        if self.hires_image is None:
            update_cache = 1
            self.hires_image = self.image
            self.image = None
        if web_format != 'unknown':
            if self.web_format != web_format:
                self.web_format = web_format
                update_cache = 1
        # check if web_scale can be parsed:
        self.getCanonicalWebScale(web_scale)
        if self.web_scale != web_scale:
            update_cache = 1
            self.web_scale = web_scale
        # check if web_crop can be parsed:
        self.getCropBox(web_crop)
        if self.web_crop != web_crop:
            update_cache = 1
            self.web_crop = web_crop
        if self.hires_image is not None and update_cache:
            self._createDerivedImages()

    security.declareProtected(
        SilvaPermissions.ChangeSilvaContent, 'set_image')
    def set_image(self, file):
        """Set the image object.
        """
        self._image_factory('hires_image', file)
        format = self.getFormat()
        if format in self.web_formats:
            self.web_format = format
        self._createDerivedImages()
        self.update_quota()

    security.declareProtected(SilvaPermissions.View, 'getCanonicalWebScale')
    def getCanonicalWebScale(self, scale=None):
        """returns (width, height) of web image"""
        if scale is None:
            scale = self.web_scale
        m = self.re_WidthXHeight.match(scale)
        if m is None:
            m = self.re_percentage.match(scale)
            if m is None:
                msg = _("'${scale}' is not a valid scale identifier. "
                        "Probably a percent symbol is missing.",
                        mapping={'scale': scale})
                msg = translate(msg)
                raise ValueError, msg
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
                msg = _("'${scale} is not a valid scale identifier. "
                        "At least one number is required.",
                        mapping={'scale': scale})
                msg = translate(msg)
                raise ValueError, msg
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
            msg = _("'${crop} is not a valid crop identifier",
                    mapping={'crop': crop})
            msg = translate(msg)
            raise ValueError, msg
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
            msg = _("'${crop}' defines an impossible cropping",
                    mapping={'crop': crop})
            msg = translate(msg)
            raise ValueError, msg
        return (x1, y1, x2, y2)

    security.declareProtected(SilvaPermissions.View, 'getDimensions')
    def getDimensions(self, img=None):
        """Returns width, heigt of (hi res) image.

        Raises ValueError if there is no way of determining the dimenstions,
        Return 0, 0 if there is no image,
        Returns width, height otherwise.
        """
        if img is None:
            img = self.hires_image
        if img is None:
            img = self.image
        if img is None:
            return (0, 0)
        try:
            width, height = self._get_dimensions_from_image_data(img)
        except TypeError:
            return (0, 0)
        return width, height

    security.declareProtected(SilvaPermissions.View, 'getFormat')
    def getFormat(self):
        """Returns image format.
        """
        if havePIL:
            return self._getPILImage(self.hires_image).format
        ct, w, h = OFS.Image.getImageInfo(self.hires_image.get_content())
        if not ct:
            raise ValueError, _(u"Unknown image format.")
        return ct.split('/')[1].upper()

    security.declareProtected(SilvaPermissions.View, 'getImage')
    def getImage(self, hires=1, webformat=0):
        """Return image data.
        """
        if hires and not webformat:
            image = self.hires_image
        elif not hires and webformat:
            image = self.image
        elif hires and webformat:
            pil_image = self._getPILImage(self.hires_image)
            have_changed, pil_image = self._prepareWebFormat(pil_image)
            image_data = StringIO()
            pil_image.save(image_data, self.web_format)
            return image_data.getvalue()
        elif not hires and not webformat:
            raise ValueError, _(u"Low resolution image in original format is "
                                u"not supported")
        return image.get_content()

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
        title = self.get_title_or_id()
        width, height = self.getDimensions(image)
        named = []

        if kw.has_key('css_class'):
            kw['class'] = kw['css_class']
            del kw['css_class']

        for name, value in kw.items():
            named.append('%s="%s"' % (escape(name, 1), escape(value, 1)))
        named = ' '.join(named)
        return '<img src="%s" width="%s" height="%s" alt="%s" %s />' % (
            img_src, width, height, escape(title, 1), named)

    security.declareProtected(SilvaPermissions.View, 'url')
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
        except (ValueError, TypeError):
            # XXX i18n - should we translate this?
            return 'unknown'

    security.declareProtected(SilvaPermissions.View, 'getWebScale')
    def getWebScale(self):
        """Return scale percentage / WxH of web presentation image
        """
        return str(self.web_scale)

    security.declareProtected(SilvaPermissions.View, 'getWebCrop')
    def getWebCrop(self):
        """Return crop identifier
        """
        return str(self.web_crop)

    security.declareProtected(SilvaPermissions.View, 'canScale')
    def canScale(self):
        """returns if scaling/converting is possible"""
        return havePIL

    security.declareProtected(SilvaPermissions.ChangeSilvaContent,
        'getFileSystemPath')
    def getFileSystemPath(self):
        """return path on filesystem for containing image"""
        return self.hires_image.getFileSystemPath()

    security.declareProtected(SilvaPermissions.View, 'getOrientation')
    def getOrientation(self):
        """Returns translated Image orientation (string).
        """
        return _(self.getOrientationClass())

    security.declareProtected(SilvaPermissions.View, 'getOrientationClass')
    def getOrientationClass(self):
        """ returns Image orientation

            untranslated string that can be used as class name
        """
        width, height = self.getDimensions()
        if width == height:
            return "square"
        elif width > height:
            return "landscape"
        return "portrait"

    def content_type(self):
        return self.image.content_type

    def get_file_size(self):
        if self.hires_image:
            return self.hires_image.get_file_size()
        return 0

    security.declareProtected(SilvaPermissions.View, 'get_scaled_file_size')
    def get_scaled_file_size(self):
        return self.image.get_file_size()

    ##########
    ## private

    def _getPILImage(self, img):
        """return PIL of an image

            raise ValueError if no PIL is available
            raise ValueError if image could not be identified
        """
        if not havePIL:
            raise ValueError, _(u"No PIL installed.")
        if img is None:
            img = self.image
        image_reference = img.get_content_fd()
        try:
            image = PIL.Image.open(image_reference)
        except IOError, e:
            raise ValueError, e.args[-1]
        return image


    def _createDerivedImages(self):
        self._createWebPresentation()
        self._createThumbnail()


    def _createWebPresentation(self):
        try:
            image = self._getPILImage(self.hires_image)
        except ValueError, e:
            logger.info("Web presentation creation failed for %s with %s" %
                        ('/'.join(self.getPhysicalPath()), str(e)))
            self.image = self.hires_image
            return

        changed = False
        cropbox = self.getCropBox()
        if cropbox:
            image = image.crop(cropbox)
            changed = True

        if self.web_scale != '100%':
            width, height = self.getCanonicalWebScale()
            image = image.resize((width, height), PIL.Image.ANTIALIAS)
            changed = True

        have_changed, image = self._prepareWebFormat(image)
        if have_changed:
            changed = True

        if not changed:
            self.image = self.hires_image
            return

        new_image_data = StringIO()
        try:
            image.save(new_image_data, self.web_format)
        except IOError, e:
            logger.info("Web presentation creation failed for %s with %s" %
                        ('/'.join(self.getPhysicalPath()), str(e)))
            if str(e.args[0]) == "cannot read interlaced PNG files":
                self.image = self.hires_image
                return
            else:
                raise ValueError, str(e)

        ct = self._web2ct[self.web_format]
        new_image_data.seek(0)
        self._image_factory('image', new_image_data, ct)


    def _createThumbnail(self):
        try:
            image = self._getPILImage(self.hires_image)
        except ValueError, e:
            logger.info("Thumbnail creation failed for %s with %s" %
                        ('/'.join(self.getPhysicalPath()), str(e)))
            # no thumbnail
            self.thumbnail_image = None
            return

        try:
            thumb = image.copy()
            ts = self.thumbnail_size
            thumb.thumbnail((ts, ts), PIL.Image.ANTIALIAS)
        except IOError, e:
            logger.info("Thumbnail creation failed for %s with %s" %
                        ('/'.join(self.getPhysicalPath()), str(e)))
            if str(e.args[0]) == "cannot read interlaced PNG files":
                self.thumbnail_image = None
                return
            else:
                raise ValueError, str(e)

        changed, thumb = self._prepareWebFormat(thumb)
        thumb_data = StringIO()
        thumb.save(thumb_data, self.web_format)
        ct = self._web2ct[self.web_format]
        thumb_data.seek(0)
        self._image_factory('thumbnail_image', thumb_data, ct)

    def _prepareWebFormat(self, image):
        """Converts image's mode if necessary. Return True on change,
        False if nothing is done.
        """

        if image.mode != 'RGB' and self.web_format == 'JPEG':
            return True, image.convert("RGB")
        return False, image

    def _image_factory(self, image_id, file, content_type=None):
        service_files = component.getUtility(interfaces.IFilesService)
        new_image = service_files.newFile(image_id)
        setattr(self, image_id, new_image)
        new_image = getattr(self, image_id)
        new_image.set_file_data(file)

        image_filename = self.getId()
        if not image_id.startswith('hires'):
            if '.' in image_filename:
                base_id, ext = os.path.splitext(image_filename)
            else:
                base_id = image_filename
            image_filename = '%s.%s' % (base_id, self.web_format.lower())
        new_image.set_filename(image_filename)

        if content_type is not None:
            new_image.set_content_type(content_type)
        return new_image

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
        if interfaces.IFileSystemFile.providedBy(image):
            # apache rewrite in effect
            img_src = image.get_download_url()
        return image, img_src

    def _image_is_hires(self):
        return (self.image is not None and
                self.image.aq_base is self.hires_image.aq_base)

    def _get_dimensions_from_image_data(self, img):
        """return width, heigth computed from image's data

            raises ValueError if the dimensions could not be determined
        """
        if havePIL:
            return self._getPILImage(img).size
        ct, w, h = OFS.Image.getImageInfo(img.get_content())
        if w <= 0 or h <= 0:
            raise ValueError, _(u"Could not identify image type.")
        return w, h

InitializeClass(Image)


class ImagePublishTraverse(SilvaPublishTraverse):

    def browserDefault(self, request):
        # We don't want to lookup five views if we have other than a
        # GET or HEAD request, but delegate to the sub-object.
        object, method = super(
            ImagePublishTraverse, self).browserDefault(request)
        if request.method in ('GET', 'HEAD',):
            query = request.QUERY_STRING
            if query == 'hires':
                img = self.context.hires_image
            elif query == 'thumbnail':
                img = self.context.thumbnail_image
            else:
                img = self.context.image
            return img, method
        return object, method


class ImageStorageConverter(object):

    grok.implements(interfaces.IUpgrader)

    def upgrade(self, image):
        if not interfaces.IImage.providedBy(image):
            return image
        file_obj = image.hires_image
        if file_obj is None:
            logger.error("No orginal data for %s, storage not changed." %
                         '/'.join(image.getPhysicalPath()))
            return image
        ct = file_obj.get_mime_type()
        data = file_obj.get_content_fd()
        image._image_factory('hires_image', data, ct)
        image._createDerivedImages()
        logger.info("Storage for image %s converted" %
                    '/'.join(image.getPhysicalPath()))
        return image


class IImageAddFields(Interface):

    file = silvaschema.Bytes(title=_(u"image"), required=True)
    title = schema.TextLine(
        title=_(u"title"),
        description=_(u"Fill in a title. It will be used for the ALT (Alternative text) attribute of the image."),
        required=True)
    id = silvaschema.ID(
        title=_(u"id"),
        description=_(u"No spaces or special characters besides ‘_’ or ‘-’ or ‘.’"),
        required=False)


class ImageAddForm(silvaz3cforms.AddForm):
    """Add form for an image.
    """

    silvaconf.context(interfaces.IImage)
    silvaconf.name(u'Silva Image')
    fields = field.Fields(IImageAddFields)

    def create(self, parent, data):
        factory = parent.manage_addProduct['Silva']
        return factory.manage_addImage(
            data['id'], data['title'], file=data['file'])


# Register Image factory for image mimetypes
import mimetypes
from Products.Silva import assetregistry
from ContentObjectFactoryRegistry import contentObjectFactoryRegistry

mt = mimetypes.types_map.values()
mt  = [mt for mt in mt if mt.startswith('image')]
assetregistry.registerFactoryForMimetypes(mt, manage_addImage, 'Silva')


def image_factory(self, id, content_type, body):
    """Create an Image.
    """
    id = mangle.Id(self, id, file=body, interface=interfaces.IAsset)
    id.cook()
    if not id.isValid():
        return None
    img = Image(str(id)).__of__(self)
    return img


def _should_create_image(id, content_type, body):
    return content_type.startswith('image/')


contentObjectFactoryRegistry.registerFactory(
    image_factory,
    _should_create_image)


@silvaconf.subscribe(
    interfaces.IImage, zope.app.container.interfaces.IObjectAddedEvent)
def image_added(image, event):
    for id in ('hires_image', 'image', 'thumbnail_image'):
        img = getattr(image, id, None)
        if img is None:
            continue
        img.id = id


@silvaconf.subscribe(
    interfaces.IImage, OFS.interfaces.IObjectClonedEvent)
def image_cloned(image, event):
    "copy support"
    for id in ('image', 'hires_image', 'thumbnail_image'):
        img = getattr(image, id, None)
        if img is None:
            continue
        img.id = id