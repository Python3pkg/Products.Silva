# Copyright (c) 2002 Infrae. All rights reserved.
# See also LICENSE.txt
# Python
import md5 
import time, datetime
# Zope
import Globals
from AccessControl import ClassSecurityInfo, ModuleSecurityInfo, allow_module
from BTrees.OOBTree import OOBTree
# Silva
from Products.Silva import interfaces
from Products.Silva import SilvaPermissions, Versioning
from Products.Silva.adapters import adapter

TIMEOUTINDAYS =  3

NOT_SUBSCRIBABLE = 0
SUBSCRIBABLE = 1
ACQUIRE_SUBSCRIBABILITY = 2

class Subscription:

    __implements__ = (interfaces.ISubscription, )

    def __init__(self, emailaddress, contentsubscribedto):
        self._emailaddress = emailaddress
        self._contentsubscribedto = contentsubscribedto
        
    def emailaddress(self):
        return self._emailaddress
    
    def contentSubscribedTo(self):
        return self._contentsubscribedto
    
class Subscribable(adapter.Adapter):
    """
    """
    
    __implements__ = (interfaces.ISubscribable, )
    
    security = ClassSecurityInfo()
    
    def __init__(self, context):
        adapter.Adapter.__init__(self, context)
        if not hasattr(self.context, '__subscribability__'):
            self.context.__subscribability__ = ACQUIRE_SUBSCRIBABILITY
        if not hasattr(self.context, '__subscriptions__'):
            self.context.__subscriptions__ = OOBTree()
        if not hasattr(self.context, '__pending_subscription_tokens__'):
            self.context.__pending_subscription_tokens__ = OOBTree()
    
    # ACCESSORS FOR UI

    security.declareProtected(
        SilvaPermissions.ChangeSilvaContent, 'isSubscribable')
    def isSubscribable(self):
        if self.context.__subscribability__ == NOT_SUBSCRIBABLE:
            return False
        subscribables = self._buildSubscribablesList()
        return bool(subscribables)
    
    security.declareProtected(
        SilvaPermissions.ChangeSilvaContent, 'subscribability')
    def subscribability(self):
        return self.context.__subscribability__

    security.declareProtected(
        SilvaPermissions.ChangeSilvaContent, 'getSubscribedEmailaddresses')
    def getSubscribedEmailaddresses(self):
        emailaddresses = list(self.context.__subscriptions__.keys())
        return emailaddresses
    
    # ACCESSORS
    
    def getSubscriptions(self):
        return self._getSubscriptions().values()
    
    def _getSubscriptions(self):
        if self.context.__subscribability__ == NOT_SUBSCRIBABLE:
            return {}
        subscriptions = {}
        subscribables = self._buildSubscribablesList()
        for subscribable in subscribables:
            for emailaddress in subscribable.getSubscribedEmailaddresses():
                if not subscriptions.has_key(emailaddress):
                    # Use aq_inner to unwrap the adapter-containment
                    contentsubscribedto = subscribable.context.aq_inner
                    subscriptions[emailaddress] = Subscription(
                        emailaddress, contentsubscribedto)
        return subscriptions
        
    def _buildSubscribablesList(self, subscribables=None, marker=0):
        if subscribables is None:
            subscribables = []
        if self.context.__subscribability__ == NOT_SUBSCRIBABLE:
            # Empty list from the point without explicit subscribability onwards.
            del subscribables[marker:]
            return subscribables
        subscribables.append(self)
        if self.context.__subscribability__ == SUBSCRIBABLE:
            # Keep a marker for the object with explicit subscribability set.
            marker = len(subscribables)
        # Use aq_inner first, to unwrap the adapter-containment.
        parent = self.context.aq_inner.aq_parent
        subscr = getSubscribable(parent)
        return subscr._buildSubscribablesList(subscribables, marker)
    
    security.declarePrivate('isValidSubscription')
    def isValidSubscription(self, emailaddress, token):
        return self._validate(emailaddress, token)

    security.declarePrivate('isValidCancellation')
    def isValidCancellation(self, emailaddress, token):
        return self._validate(emailaddress, token)

    security.declarePrivate('isSubscribed')
    def isSubscribed(self, emailaddress):
        subscriptions = self.context.__subscriptions__
        return bool(subscriptions.has_key(emailaddress))
        
    security.declarePrivate('getSubscription')
    def getSubscription(self, emailaddress):
        subscriptions = self._getSubscriptions()
        return subscriptions.get(emailaddress, None)
    
    # MODIFIERS

    security.declareProtected(
        SilvaPermissions.ChangeSilvaContent, 'setSubscribability')
    def setSubscribability(self, flag):
        self.context.__subscribability__ = flag
    
    security.declareProtected(
        SilvaPermissions.ChangeSilvaContent, 'subscribe')
    def subscribe(self, emailaddress):
        subscriptions = self.context.__subscriptions__
        subscriptions[emailaddress] = None

    security.declareProtected(
        SilvaPermissions.ChangeSilvaContent, 'unsubscribe')
    def unsubscribe(self, emailaddress):
        subscriptions = self.context.__subscriptions__
        if subscriptions.has_key(emailaddress):
            del subscriptions[emailaddress]

    security.declarePrivate('generateConfirmationToken')
    def generateConfirmationToken(self, emailaddress):
        tokens = self.context.__pending_subscription_tokens__
        timestamp = time.time()
        token = self._generateToken(emailaddress, '%f' % timestamp)
        tokens[emailaddress] = (timestamp, token)
        return token
    
    def _generateToken(self, *args):
        s = md5.new()
        for arg in args:
            s.update(arg)
        return s.hexdigest()
    
    def _validate(self, emailaddress, token):
        # The current implementation will keep items in the
        # pending list indefinitly if _validate is not called (end user
        # doesn't follow up on confirmantion email), or _validate is called,
        # but the supplied token is not valid.
        tokens = self.context.__pending_subscription_tokens__
        timestamp, validation_token = tokens.get(emailaddress,(None, None))
        if timestamp is None or validation_token is None:
            return False
        now = datetime.datetime.now()
        then = datetime.datetime.fromtimestamp(timestamp)
        delta = now - then
        if delta.days > TIMEOUTINDAYS:
            del tokens[emailaddress]
            return False
        if token == validation_token:
            del tokens[emailaddress]
            return True
        return False

Globals.InitializeClass(Subscribable)

class SubscribableRoot(Subscribable):

    security = ClassSecurityInfo()

    __implements__ = (interfaces.ISubscribable, )
    
    def __init__(self, context):
        adapter.Adapter.__init__(self, context)
        if not hasattr(self.context, '__subscribability__'):
            self.context.__subscribability__ = NOT_SUBSCRIBABLE
        if not hasattr(self.context, '__subscriptions__'):
            self.context.__subscriptions__ = OOBTree()
        if not hasattr(self.context, '__pending_subscription_tokens__'):
            self.context.__pending_subscription_tokens__ = OOBTree()
    
    def _buildSubscribablesList(self, subscribables=None, marker=0):
        # Overrides Subscribable._buildSubscribablesList to stop recursion.
        if subscribables is None:
            subscribables = []
        if self.context.__subscribability__ == NOT_SUBSCRIBABLE:
            # Empty list from the point without explicit subscribability onwards.
            del subscribables[marker:]
            return subscribables
        subscribables.append(self)
        return subscribables

Globals.InitializeClass(SubscribableRoot)
    
# Jumping through security hoops to get the adapter
# somewhat accessible to Python scripts

allow_module('Products.Silva.adapters.subscribable')

__allow_access_to_unprotected_subobjects__ = True
    
module_security = ModuleSecurityInfo('Products.Silva.adapters.subscribable')
    
module_security.declareProtected(
    SilvaPermissions.ChangeSilvaContent, 'getSubscribable')
def getSubscribable(context):
    if interfaces.IRoot.isImplementedBy(context):
        return SubscribableRoot(context).__of__(context)
    if interfaces.IContainer.isImplementedBy(context):
        return Subscribable(context).__of__(context)
    if interfaces.IContent.isImplementedBy(context):
        return Subscribable(context).__of__(context)
    return None
