# Copyright (c) 2002-2008 Infrae. All rights reserved.
# See also LICENSE.txt
# $Id: VirtualGroup.py,v 1.18 2006/01/24 16:14:13 faassen Exp $
from zope.interface import implements

from AccessControl import ClassSecurityInfo, Unauthorized
from Globals import InitializeClass
from Products.PageTemplates.PageTemplateFile import PageTemplateFile
# Silva
import SilvaPermissions

from interfaces import IVirtualGroup
from Group import BaseGroup, manage_addGroupUsingFactory

class VirtualGroup(BaseGroup):
    """Silva Virtual Group"""

    meta_type = "Silva Virtual Group"    
    security = ClassSecurityInfo()
    
    implements(IVirtualGroup)

    manage_main = PageTemplateFile('www/virtualGroupEdit', globals())
    
    # MANIPULATORS
    security.declareProtected(
        SilvaPermissions.ChangeSilvaAccess, 'addGroup')
    def addGroup(self, group):
        """add a group to the virtual group"""
        if not self.isValid():
            raise Unauthorized, "Zombie group asset"
        
        self.service_groups.addGroupToVirtualGroup(group, self._group_name)

    security.declareProtected(
        SilvaPermissions.ChangeSilvaAccess, 'copyGroupsFromVirtualGroups')
    def copyGroupsFromVirtualGroups(self, virtual_groups):
        sg = self.service_groups
        groups = {}
        for virtual_group in virtual_groups:        
            if sg.isVirtualGroup(virtual_group):
                for group in sg.listGroupsInVirtualGroup(virtual_group):
                    groups[group] = 1
        current_groups = self.listGroups()
        groupids = [groupid for groupid in groups.keys() 
                    if groupid not in current_groups]
        for groupid in groupids:
            self.addGroup(groupid)
        # For UI feedback
        return groupids

    security.declareProtected(
        SilvaPermissions.ChangeSilvaAccess, 'removeGroup')
    def removeGroup(self, group):
        """removes a group from the vgroup"""
        if not self.isValid():
            raise Unauthorized, "Zombie group asset"
        self.service_groups.removeGroupFromVirtualGroup(
            group, self._group_name)
    
    # ACCESSORS    
    security.declareProtected(
        SilvaPermissions.ChangeSilvaAccess, 'listGroups')
    def listGroups(self):
        """list groups in this vgroup"""
        if not self.isValid():
            raise Unauthorized, "Zombie group asset"
        result = self.service_groups.listGroupsInVirtualGroup(self._group_name)
        result.sort()
        return result

InitializeClass(VirtualGroup)

def manage_addVirtualGroup(*args, **kwargs):
    """Add a Virtual Group."""
    return manage_addGroupUsingFactory(VirtualGroup, *args, **kwargs)


