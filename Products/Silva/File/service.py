# -*- coding: utf-8 -*-
# Copyright (c) 2002-2010 Infrae. All rights reserved.
# See also LICENSE.txt

import logging

# Zope 3
from five import grok
from zope.app.schema.vocabulary import IVocabularyFactory
from zope.location.interfaces import ISite
from zope.schema.fieldproperty import FieldProperty
from zope.schema.vocabulary import SimpleTerm, SimpleVocabulary
from zope.interface import directlyProvides

# Zope 2
from AccessControl import ClassSecurityInfo
from Acquisition import aq_parent
from App.class_init import InitializeClass

# Silva
from Products.Silva.Image.content import ImageStorageConverter
from Products.Silva.File.content import BlobFile, ZODBFile
from silva.core import conf as silvaconf
from silva.core import interfaces
from silva.core.services.base import SilvaService
from silva.core.services.interfaces import IFilesService
from silva.core.upgrade import upgrade
from silva.translations import translate as _
from zeam.form import silva as silvaforms

logger = logging.getLogger('silva.file')



def FileStorageTypeVocabulary(context):
    terms = [SimpleTerm(value=ZODBFile, title='ZODB File', token='ZODBFile'),
             SimpleTerm(value=BlobFile, title='Blob File', token='BlobFile'),]
    return SimpleVocabulary(terms)

directlyProvides(FileStorageTypeVocabulary, IVocabularyFactory)


class FilesService(SilvaService):
    meta_type = 'Silva Files Service'
    grok.implements(IFilesService)
    grok.name('service_files')
    silvaconf.default_service()
    silvaconf.icon('www/files_service.gif')

    security = ClassSecurityInfo()

    storage = FieldProperty(IFilesService['storage'])

    manage_options = (
        {'label':'Settings', 'action':'manage_settings'},
        ) + SilvaService.manage_options

    security.declarePrivate('new_file')
    def new_file(self, id):
        if self.storage is None:
            return ZODBFile(id)
        return self.storage(id)

    def is_file_using_correct_storage(self, content):
        storage = ZODBFile
        if self.storage is not None:
            storage = self.storage
        return isinstance(content, storage)


InitializeClass(FilesService)


class FileServiceManagementView(silvaforms.ZMIComposedForm):
    """Edit File Service.
    """
    grok.require('zope2.ViewManagementScreens')
    grok.name('manage_settings')
    grok.context(FilesService)

    label = _(u"Configure file storage")


class FileServiceSettings(silvaforms.ZMISubForm):
    grok.context(FilesService)
    silvaforms.view(FileServiceManagementView)
    silvaforms.order(10)

    label = _(u"Select storage")
    fields = silvaforms.Fields(IFilesService)
    actions = silvaforms.Actions(silvaforms.EditAction())
    ignoreContent = False


class FileServiceConvert(silvaforms.ZMISubForm):
    grok.context(FilesService)
    silvaforms.view(FileServiceManagementView)
    silvaforms.order(20)

    label = _(u"Convert stored files")
    description = _(u"Convert all currently stored file to "
                    u"the current set storage")

    @silvaforms.action(_(u'Convert all files'))
    def convert(self):
        parent = self.context.get_publication()
        service = self.context
        upg = upgrade.UpgradeRegistry()
        upg.registerUpgrader(
            StorageConverterHelper(parent), '0.1', upgrade.AnyMetaType)
        upg.registerUpgrader(
            FileStorageConverter(service), '0.1', 'Silva File')
        upg.registerUpgrader(
            ImageStorageConverter(service), '0.1', 'Silva Image')
        upg.upgradeTree(parent, '0.1')
        self.status = _(u'Storage for Silva Files and Images converted. '
                        u'Check the log for more details.')


class StorageConverterHelper(object):
    """The purpose of this converter is to stop convertion if there is
    an another configuration.
    """
    grok.implements(interfaces.IUpgrader)

    def __init__(self, publication):
        self.startpoint = publication

    def validate(self, context):
        if context is self.startpoint:
            return False

        if ISite.providedBy(context):
            for obj in context.objectValues():
                if IFilesService.providedBy(obj):
                    raise StopIteration()
        return False

    def upgrade(self, context):
        return context


class FileStorageConverter(object):
    """Convert storage for a file.
    """
    grok.implements(interfaces.IUpgrader)

    def __init__(self, service):
        self.service = service

    def validate(self, content):
        if not interfaces.IFile.providedBy(content):
            return False
        if self.service.is_file_using_correct_storage(content):
            # don't convert that are already correct
            return False
        return True

    def upgrade(self, content):
        data = content.get_file_fd()
        id = content.getId()
        title = content.get_title()
        content_type = content.get_content_type()

        new_file = self.service.new_file(id)
        container = aq_parent(content)
        new_file = container._getOb(id)
        new_file.set_title(title)
        new_file.set_file(data)
        new_file.set_content_type(content_type)

        logger.info("File %s migrated" %
                    '/'.join(new_file.getPhysicalPath()))
        return new_file

