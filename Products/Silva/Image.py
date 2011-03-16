# -*- coding: utf-8 -*-
# Copyright (c) 2002-2010 Infrae. All rights reserved.
# See also LICENSE.txt
# $Id$

from __future__ import absolute_import

# Python
import re
import logging
import mimetypes
from cStringIO import StringIO
from cgi import escape
import os.path

logger = logging.getLogger('silva.image')

# Zope 3
from five import grok
from zope import component
from zope import schema
from zope.component import getMultiAdapter
from zope.event import notify
from zope.interface import Interface
from zope.lifecycleevent import ObjectCreatedEvent
from zope.lifecycleevent import ObjectModifiedEvent
from zope.lifecycleevent.interfaces import IObjectMovedEvent
from zope.schema.vocabulary import SimpleVocabulary, SimpleTerm

# Zope 2
from AccessControl import ClassSecurityInfo
from App.class_init import InitializeClass

# Silva
from Products.Silva import assetregistry
from Products.Silva import mangle, SilvaPermissions
from Products.Silva.Asset import Asset, SMIAssetPortlet
from Products.Silva.Asset import AssetEditTab
from Products.Silva.helpers import create_new_filename
from Products.Silva.ContentObjectFactoryRegistry import \
    contentObjectFactoryRegistry

from silva.core.conf.interfaces import ITitledContent
from silva.core import conf as silvaconf
from silva.core import interfaces
from silva.core.conf import schema as silvaschema
from silva.core.views import views as silvaviews
from silva.core.views.traverser import SilvaPublishTraverse
from silva.translations import translate as _
from silva.core.views.interfaces import ISilvaURL, INonCachedLayer

from zeam.form import silva as silvaforms
from zeam.form.base import NO_VALUE

try:
    from PIL import Image as PILImage
except ImportError:
    import Image as PILImage
havePIL = 1


def manage_addImage(context, id, title, file=None, REQUEST=None):
    """Add an Image.
    """
    if file is not None:
        try:
            # Try to validate file format.
            if hasattr(file, 'seek'):
                file.seek(0)
            PILImage.open(file)
        except IOError, error:
            raise ValueError(error.args[-1].capitalize())
        # Come back at the begining..
        file.seek(0)

    content = image_factory(context, id, None, file)
    if content is None:
        raise ValueError(_(u"Invalid computed identifier."))
    id = content.getId()
    if id in context.objectIds():
        raise ValueError(
            _(u"Duplicate id. Please provide an explicit id."))
    context._setObject(id, content)
    content = getattr(context, id)
    content.set_title(title)
    if file:
        content.set_image(file)
    notify(ObjectCreatedEvent(content))
    return content


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
    web_formats = ('JPEG', 'GIF', 'PNG',)
    web_crop = ''

    _web2ct = {
        'JPEG': 'image/jpeg',
        'GIF': 'image/gif',
        'PNG': 'image/png',
    }

    silvaconf.priority(-3)
    silvaconf.icon('www/silvaimage.gif')
    silvaconf.factory('manage_addImage')

    security.declareProtected(
        SilvaPermissions.ChangeSilvaContent, 'set_web_presentation_properties')
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
            if self.web_format != web_format and \
                    web_format in self.web_formats:
                self.web_format = web_format
                update_cache = 1
        # check if web_scale can be parsed:
        self.get_canonical_web_scale(web_scale)
        if self.web_scale != web_scale:
            update_cache = 1
            self.web_scale = web_scale
        # check if web_crop can be parsed:
        self.get_crop_box(web_crop)
        if self.web_crop != web_crop:
            update_cache = 1
            self.web_crop = web_crop
        if self.hires_image is not None and update_cache:
            self._createDerivedImages()
        notify(ObjectModifiedEvent(self))

    security.declareProtected(
        SilvaPermissions.ChangeSilvaContent, 'set_image')
    def set_image(self, file):
        """Set the image object.
        """
        self._image_factory('hires_image', file)
        format = self.get_format()
        if format in self.web_formats:
            self.web_format = format
        self._createDerivedImages()
        notify(ObjectModifiedEvent(self))

        # XXX Should be on event
        self.update_quota()

    security.declareProtected(SilvaPermissions.View, 'get_canonical_web_scale')
    def get_canonical_web_scale(self, scale=None):
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
                raise ValueError(msg)
            cropbox = self.get_crop_box()
            if cropbox:
                x1, y1, x2, y2 = cropbox
                width = x2 - x1
                height = y2 - y1
            else:
                width, height = self.get_dimensions()
            percentage = float(m.group(1))/100.0
            width = int(width * percentage)
            height = int(height * percentage)
        else:
            img_w, img_h = self.get_dimensions()
            width = m.group(1)
            height = m.group(2)
            if width == height == '*':
                msg = _("'${scale} is not a valid scale identifier. "
                        "At least one number is required.",
                        mapping={'scale': scale})
                raise ValueError(msg)
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

    security.declareProtected(SilvaPermissions.View, 'get_crop_box')
    def get_crop_box(self, crop=None):
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
            raise ValueError(msg)
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
            raise ValueError(msg)
        return (x1, y1, x2, y2)

    security.declareProtected(SilvaPermissions.View, 'get_dimensions')
    def get_dimensions(self, img=None):
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

    security.declareProtected(SilvaPermissions.View, 'get_format')
    def get_format(self):
        """Returns image format.
        """
        return self._getPILImage(self.hires_image).format

    security.declareProtected(SilvaPermissions.View, 'get_image')
    def get_image(self, hires=1, webformat=0):
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
            raise ValueError(_(u"Low resolution image in original format is "
                               u"not supported"))
        return image.get_content()


    security.declareProtected(SilvaPermissions.View, 'tag')
    def tag(self, hires=0, thumbnail=0, **extra_attributes):
        """ return xhtml tag

        Since 'class' is a Python reserved word, it cannot be passed in
        directly in keyword arguments which is a problem if you are
        trying to use 'tag()' to include a CSS class. The tag() method
        will accept a 'css_class' argument that will be converted to
        'class' in the output tag to work around this.
        """
        image, img_src = self._get_image_and_src(hires, thumbnail)
        title = self.get_title_or_id()
        width, height = self.get_dimensions(image)
        named = []

        if extra_attributes.has_key('css_class'):
            extra_attributes['class'] = extra_attributes['css_class']
            del extra_attributes['css_class']

        for name, value in extra_attributes.items():
            named.append('%s="%s"' % (escape(name, 1), escape(value, 1)))
        named = ' '.join(named)
        return '<img src="%s" width="%s" height="%s" alt="%s" %s />' % (
            img_src, width, height, escape(title, 1), named)

    security.declareProtected(SilvaPermissions.View, 'url')
    def url(self, hires=0, thumbnail=0):
        "return url of image"
        image, img_src = self._get_image_and_src(hires, thumbnail)
        return img_src

    security.declareProtected(SilvaPermissions.View, 'get_web_format')
    def get_web_format(self):
        """Return file format of web presentation image
        """
        try:
            return self._getPILImage(self.image).format
        except (ValueError, TypeError):
            # XXX i18n - should we translate this?
            return 'unknown'

    security.declareProtected(SilvaPermissions.View, 'get_web_scale')
    def get_web_scale(self):
        """Return scale percentage / WxH of web presentation image
        """
        return str(self.web_scale)

    security.declareProtected(SilvaPermissions.View, 'get_web_crop')
    def get_web_crop(self):
        """Return crop identifier
        """
        return str(self.web_crop)

    security.declareProtected(SilvaPermissions.ChangeSilvaContent,
        'get_file_system_path')
    def get_file_system_path(self):
        """return path on filesystem for containing image"""
        return self.hires_image.get_file_system_path()

    security.declareProtected(SilvaPermissions.View, 'get_orientation')
    def get_orientation(self):
        """Returns translated Image orientation (string).
        """
        width, height = self.get_dimensions()
        if width == height:
            return _("square")
        elif width > height:
            return _("landscape")
        return _("portrait")

    security.declareProtected(
        SilvaPermissions.AccessContentsInformation, 'get_filename')
    def get_filename(self):
        if self.image is None:
            return self.getId()
        return self.image.get_filename()

    security.declareProtected(
        SilvaPermissions.AccessContentsInformation, 'get_mime_type')
    def get_mime_type(self):
        if self.image is None:
            return 'application/octet-stream'
        return self.image.get_mime_type()

    security.declareProtected(
        SilvaPermissions.AccessContentsInformation, 'content_type')
    def content_type(self):
        if self.image is None:
            return 'application/octet-stream'
        return self.image.content_type()

    security.declareProtected(
        SilvaPermissions.AccessContentsInformation, 'get_file_size')
    def get_file_size(self):
        if self.image is None:
            return 0
        return self.image.get_file_size()

    ##########
    ## private

    def _getPILImage(self, img):
        """return PIL of an image

            raise ValueError if no PIL is available
            raise ValueError if image could not be identified
        """
        if img is None:
            img = self.image
            if img is None:
                img = self.hires_image
                if img is None:
                    raise ValueError(u"Image missing.")
        image_reference = img.get_content_fd()
        try:
            image = PILImage.open(image_reference)
        except IOError, error:
            raise ValueError(error.args[-1].capitalize())
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
        cropbox = self.get_crop_box()
        if cropbox:
            image = image.crop(cropbox)
            changed = True

        if self.web_scale != '100%':
            width, height = self.get_canonical_web_scale()
            image = image.resize((width, height), PILImage.ANTIALIAS)
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
            thumb.thumbnail((ts, ts), PILImage.ANTIALIAS)
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
        try:
            thumb.save(thumb_data, self.web_format)
        except:
            # Some images can not be saved as thumbnail. Bug in PIL.
            self.thumbnail_image = None
            return

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

    def _image_factory(self, image_id, image_file, content_type=None):
        service_files = component.getUtility(interfaces.IFilesService)
        new_image = service_files.new_file(image_id)
        setattr(self, image_id, new_image)
        new_image = getattr(self, image_id)
        new_image.set_file_data(image_file)
        if content_type is not None:
            new_image.set_content_type(content_type)
        create_new_filename(new_image, self.getId())
        return new_image

    def _get_image_and_src(self, hires=0, thumbnail=0):
        request = self.REQUEST
        absolute_url = getMultiAdapter((self, request), ISilvaURL)
        img_src = absolute_url.url(preview=INonCachedLayer.providedBy(request))
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
        return self._getPILImage(img).size

InitializeClass(Image)


# Views

class DefaultImageView(silvaviews.View):
    """View a Image in the SMI / preview. For this just return a
    tag.

    Note that if you ask directly the URL of the image, you will
    get it, not this view (See the traverser below).
    """
    grok.context(Image)
    grok.require('zope2.View')

    def render(self):
        return self.content.tag()


class ImagePublishTraverse(SilvaPublishTraverse):

    def browserDefault(self, request):
        # We don't want to lookup five views if we have other than a
        # GET or HEAD request, but delegate to the sub-object.
        content, method = super(ImagePublishTraverse, self).browserDefault(
            request)
        if request.method in ('GET', 'HEAD',):
            query = request.QUERY_STRING
            if query == 'hires':
                img = self.context.hires_image
            elif query == 'thumbnail':
                img = self.context.thumbnail_image
            else:
                img = self.context.image
            view = getMultiAdapter((img, request), Interface, name='index.html')
            view.__parent__ = img
            method = {'GET': tuple(), 'HEAD': ('HEAD',)}.get(request.method)
            return (view, method)
        return content, method


# SMI forms

class IImageAddFields(ITitledContent):

    file = silvaschema.Bytes(title=_(u"image"), required=True)


class ImageAddForm(silvaforms.SMIAddForm):
    """Add form for an image.
    """
    grok.context(interfaces.IImage)
    grok.name(u'Silva Image')

    fields = silvaforms.Fields(IImageAddFields)
    fields['id'].required = False

    def _add(self, parent, data):
        default_id = data['id'] is not NO_VALUE and data['id'] or u''
        factory = parent.manage_addProduct['Silva']
        return factory.manage_addImage(
            default_id, data['title'], file=data['file'])


class ImageEditForm(silvaforms.SMISubForm):
    """ Edit image attributes
    """
    grok.context(interfaces.IImage)
    grok.view(AssetEditTab)
    grok.order(10)

    label = _(u'Edit')
    ignoreContent = False
    dataManager = silvaforms.SilvaDataManager

    fields = silvaforms.Fields(IImageAddFields).omit('id')
    actions  = silvaforms.Actions(silvaforms.CancelEditAction(), silvaforms.EditAction())

image_formats = SimpleVocabulary([SimpleTerm(title=u'jpg', value='JPEG'),
                                  SimpleTerm(title=u'png', value='PNG'),
                                  SimpleTerm(title=u'gif', value='GIF')])


class IFormatAndScalingFields(Interface):
    web_format = schema.Choice(
        source=image_formats,
        title=_(u"web format"),
        description=_(u"Image format for web."))
    web_scale = schema.TextLine(
        title=_(u"scaling"),
        description=_(u'Image scaling for web: use width x  '
                      u'height in pixels, or one axis length, ',
                      u'or a percentage (100x200, 100x*, *x200, 40%).'),
        required=False)
    web_crop = silvaschema.CropCoordinates(
        title=_(u"cropping"),
        description=_(u"Image cropping for web: use the"
                      u" ‘set crop coordinates’ "
                      u"button, or enter X1xY1-X2xY2"
                      u" to define the cropping box."),
        required=False)


class ImageFormatAndScalingForm(silvaforms.SMISubForm):
    """ form to resize / change format of image.
    """
    grok.context(interfaces.IImage)
    grok.view(AssetEditTab)
    grok.order(20)

    ignoreContent = False
    dataManager = silvaforms.SilvaDataManager

    label = _('Format and scaling')
    fields = silvaforms.Fields(IFormatAndScalingFields)
    fields['web_format'].mode = 'radio'
    fields['web_scale'].defaultValue = '100%'

    @silvaforms.action(title=_('Change'),
                       identifier=_('set_properties'))
    def set_properties(self):
        data, errors = self.extractData()
        if errors:
            return silvaforms.FAILURE
        try:
            self.context.set_web_presentation_properties(
                data.getWithDefault('web_format'),
                data.getWithDefault('web_scale'),
                data.getWithDefault('web_crop'))
        except ValueError as e:
            self.send_message(unicode(e), type='error')
        else:
            self.send_message(_('Scaling and/or format changed.'),
                type='feedback')
        return silvaforms.SUCCESS


class InfoPortlet(SMIAssetPortlet):
    grok.context(interfaces.IImage)
    grok.order(10)

    def update(self):
        self.format = self.context.web_format.lower()
        self.dimensions = None
        try:
            dimensions = self.context.get_dimensions()
            self.dimensions = dict(zip(['width', 'height'], dimensions))
        except ValueError:
            dimensions = None
        self.scaling = None
        if self.context.hires_image is not None:
            try:
                scaled_dimensions = self.context.get_canonical_web_scale()
                if scaled_dimensions != dimensions:
                    self.scaling = dict(zip(['width', 'height'], scaled_dimensions))
            except ValueError:
                scaled_dimensions = None
        self.thumbnail = None
        if self.context.thumbnail_image:
            self.thumbnail = self.context.tag(thumbnail=1)
        self.original =self.context.url(hires=1)
        self.orientation = self.context.get_orientation()
        self.orientation_cls = unicode(self.orientation)

# Management helpers

class ImageStorageConverter(object):
    """Convert image storage.
    """
    grok.implements(interfaces.IUpgrader)

    def __init__(self, service):
        self.service = service

    def validate(self, image):
        if not interfaces.IImage.providedBy(image):
            return False
        if image.hires_image is None:
            logger.error(
                "No orginal data for %s, storage not changed." %
                '/'.join(image.getPhysicalPath()))
            return False
        if self.service.is_file_using_correct_storage(image.hires_image):
            # don't convert that are already correct
            return False
        return True

    def upgrade(self, image):
        image_file = image.hires_image
        content_type = image_file.get_mime_type()
        data = image_file.get_content_fd()
        image._image_factory('hires_image', data, content_type)
        image._createDerivedImages()
        logger.info(
            "Storage for image %s converted" %
            '/'.join(image.getPhysicalPath()))
        return image


mt = mimetypes.types_map.values()
mt  = [mt for mt in mt if mt.startswith('image')]
assetregistry.registerFactoryForMimetypes(mt, manage_addImage, 'Silva')


def image_factory(self, id, content_type, file):
    """Create an Image.
    """
    filename = None
    if hasattr(file, 'name'):
        filename = os.path.basename(file.name)
    id = mangle.Id(self, id or filename,
        file=file, interface=interfaces.IAsset)
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


@grok.subscribe(interfaces.IImage, IObjectMovedEvent)
def image_added(image, event):
    if image is not event.object or event.newName is None:
        return
    for file_id in ('hires_image', 'image', 'thumbnail_image'):
        image_file = getattr(image, file_id, None)
        if image_file is None:
            continue
        create_new_filename(image_file, event.newName)
