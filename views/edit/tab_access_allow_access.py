## Script (Python) "tab_access_allow_access"
##bind container=container
##bind context=context
##bind namespace=
##bind script=script
##bind subpath=traverse_subpath
##parameters=
##title=
##
view = context
request = view.REQUEST
model = request.model

if not request.has_key('requests') or not request['requests']:
    return view.tab_access(message_type='error', message='No requests selected')

messages = []
for userid, role in [r.split('|') for r in request['requests']]:
    try:
        model.allow_role(userid, role)
    except Exception, e:
        return view.tab_access(message_type='error', message=e) 
    messages.append('%s allowed the %s role' % (userid, role))

model.send_messages()

return view.tab_access(message_type='feedback', message=', '.join(messages))
