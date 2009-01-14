# -*- coding: utf-8 -*-
# Copyright (c) 2008-2009 Infrae. All rights reserved.
# See also LICENSE.txt
# $Id$

from silva.core import conf as silvaconf

silvaconf.extensionName('SimpleTestExtension')
silvaconf.extensionTitle('Simple Test Extension')

from silva.core.conf.installer import DefaultInstaller
from zope.interface import Interface

class ISimpleTestExtension(Interface):
    """The default installer use an interface to known if an extension
    is installed.

    So you need to define a specific interface for your extension.
    """

install = DefaultInstaller('SimpleTestExtension', ISimpleTestExtension)