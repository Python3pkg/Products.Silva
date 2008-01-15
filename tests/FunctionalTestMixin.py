import re, os.path
import unittest
import SilvaTestCase
from urllib2 import HTTPError
from Products.Five.testbrowser import Browser

# Expected state of creation
fail_login = object()
fail_nothing_addable = object()
fail_not_addable = object()
success = object()

def openFile(filename):
    name = os.path.dirname(__file__)
    return open(name + '/' + filename)

class MixinLoginLogout(object):
    """ Test login and logout in the Silva SMI for specific roles """
    
    def do_login(self, browser, url, username, password):
        """ Login to a url with username and password"""
        # make sure we can not use the edit page if we're not logged in
        try:
            browser.open(url)
        except HTTPError, err:
            self.assertEquals(str(err), 'HTTP Error 401: Unauthorized')
        else:
            self.fail()
        # now we'll try to login
        browser.addHeader('Authorization', 'Basic %s:%s' % (
                          username, password))
        browser.addHeader('Accept-Language', 'en-US')
        browser.open(url)
        self.assertEquals(url, browser.url)
    
    def do_logout(self, browser):
        # now, let's log out again..
        root_url = self.getRoot().absolute_url()
        logout_url = '%s/manage_zmi_logout' % root_url
        try:
            browser.open(logout_url)
        except HTTPError, err:
            self.assertEquals(str(err), 'HTTP Error 401: Unauthorized')
        else:
            self.fail()
        self.assertEquals('You have been logged out.' in browser.contents, True)
        return Browser()

class MixinFieldParameters(object):
    
    def fill_create_image_fields(self, browser):
        self.fill_create_title_field(browser)
        self.fill_create_image_field(browser)

    def fill_create_file_fields(self, browser):
        self.fill_create_title_field(browser)
        self.fill_create_file_field(browser)

    def fill_create_link_fields(self, browser):
        self.fill_create_title_field(browser)
        self.fill_create_url_field(browser)
        self.fill_create_link_type_field(browser)

    def fill_create_image_field(self, browser):
        browser.getControl(name='field_file').add_file(openFile('torvald.jpg'), 'image/jpeg', 'torvald.jpg')

    def fill_create_file_field(self, browser):
        browser.getControl(name='field_file').add_file(openFile('test_role_content_types.py'), 'text/plain', 'test.txt')

    def fill_create_url_field(self, browser):
        browser.getControl(name='field_url').value = 'index'

    def fill_create_link_type_field(self, browser):
        browser.getControl(name='field_link_type').value = ['absolute']
                             
    def fill_create_title_field(self, browser):
        browser.getControl(name='field_object_title').value = 'test content'

    def fill_create_folderish_field(self, browser):
        self.fill_create_title_field(browser)
        browser.getControl(name='field_policy_name').value = ['Silva Document']
    
    def fill_create_depth_field(self, browser):
        self.fill_create_title_field(browser)
        browser.getControl(name='field_depth').value = '-1'

    def fill_create_ghost_url_field(self, browser):
        browser.getControl(name='field_content_url').value = 'index'

class MixinRoleContent(MixinLoginLogout):

    item_id = 'test_content'

    def role_logout(self, browser):
        self.do_logout(browser)
        self.assertEquals('You have been logged out.' in browser.contents, True)

    def role_login_edit(self, browser, user_name, result, base=None):
        role = SilvaTestCase.users[user_name]['role']
        password = SilvaTestCase.users[user_name]['password']
        if base is None:
            url = '%s/edit' % self.getRoot().absolute_url()
        else:
            url = '%s/%s/edit' % (self.getRoot().absolute_url(), base)

        # Try login
        try:
            self.do_login(browser, url, user_name, password)
        except HTTPError, err:
            if result is fail_login:
                self.assertEquals(str(err), 'HTTP Error 401: Unauthorized')
            else:
                self.fail()

        # Check the role
        p = re.compile('logout\s+%s' % role)
        p.findall(browser.contents)
        self.failUnless(p, 'The role does not match logout message')

    def do_create_content(self, browser, content_type, creator, result):
        # Test if role has access to no content_types
        try:
            meta_type = browser.getControl(name="meta_type")
        except LookupError:
            if result is fail_nothing_addable:
                return
            self.fail()
        # Test if role has access to content_type
        if result is fail_not_addable:
            self.failIf(content_type in meta_type.options, 'Role can access meta_type')
        else:
            self.failUnless(content_type in meta_type.options, 'Content type is not included as meta_type')
            # Create the content 
            browser.getControl(name='meta_type').value = [content_type]
            browser.getControl(name='add_object:method').click()
            browser.getControl(name='field_object_id').value = self.item_id
            # Check for special fields
            if creator:
               creator(browser)
            browser.getControl(name='add_submit').click()
            #import pdb; pdb.set_trace()
            self.failUnless('Added %s' % content_type in browser.contents, 'Content type is not included in submit feedback message')
            self.failUnless(self.item_id in browser.contents)

    def do_delete_content(self, browser):
        # Delete the content
        browser.getControl(name='ids:list').value = [self.item_id]
        browser.getControl(name='tab_edit_delete:method').click()
        self.failUnless('Deleted' in browser.contents)

    def do_make_content(self, user_name, content_type, creator, result, base=None, delete=True):
        """
            this method takes a role, logs the user (role) in, selects a content
            type, makes the content type, then deletes the content type, and 
            then logs the user out
        """
        browser = Browser()
        self.role_login_edit(browser, user_name, result, base=base)
        if result is fail_login:
            return
        self.do_create_content(browser, content_type, creator, result)
        if result is success and delete:
            self.do_delete_content(browser)
        self.role_logout(browser)

    def do_login_and_delete_content(self, user_name, result, base=None):
        browser = Browser()
        self.role_login_edit(browser, user_name, result, base=base)
        if result is fail_login:
            return
        self.do_delete_content(browser)
        self.role_logout(browser)
