## Script (Python) "tab_access_allow_and_approve"
##bind container=container
##bind context=context
##bind namespace=
##bind script=script
##bind subpath=traverse_subpath
##parameters=
##title=
##
from Products.Silva.i18n import translate as _

view = context
request = view.REQUEST
model = request.model

if not request.has_key('requests') or not request['requests']:
    return view.tab_access(message_type='error', message=_('No requests selected'))

messages = []
for userid, role in [r.split('|') for r in request['requests']]:
    view.service_members.get_member(userid).approve()
    model.allow_role(userid, role)
    msg = _('&#xab;${user_id}&#xbb; approved and allowed the ${role} role')
    msg.mapping = {'user_id': userid, 'role': role}
    messages.append(str(msg))

model.send_messages()

return view.tab_access(message_type='feedback', message=', '.join(messages))
