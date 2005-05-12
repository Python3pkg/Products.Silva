##parameters=ids=None
from Products.Silva.i18n import translate as _

request = context.REQUEST
model = request.model
view = context

from DateTime import DateTime
now = DateTime()

obj = model
message = _('Content is published')
message_type = 'feedback'
publish = True
if not obj.implements_versioning():
    message = _('not a versionable object')
    message_type = 'error'
    publish = False
elif obj.is_version_approved():
    message = _('version already approved')
    message_type = 'error'
    publish = False
elif not obj.can_approve():
    message = _('content object or one of its containers is deactivated')
    message_type = 'error'
    publish = False
if not obj.get_unapproved_version():
    if obj.is_version_published():
        message = _('version already public')
        message_type = 'error'
        publish = False
    obj.create_copy()
    
if publish:
    # publish
    obj.set_unapproved_version_publication_datetime(now)
    obj.approve_version()

    if hasattr(context, 'service_messages'):
        context.service_messages.send_pending_messages()

request.form['message_type'] = message_type
request.form['message'] = unicode(message)
request.form['show_buttons'] = True
return model.preview_html()
