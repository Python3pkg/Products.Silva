##parameters=groups=None
from Products.Silva.i18n import translate as _

request = context.REQUEST
model = request.model
view = context

userids = {}

if not groups:
    return view.tab_edit(
        message_type="error", 
        message=_("No group(s) selected, so nothing to use to add users."))

added = model.copyUsersFromGroups(groups)
if added:
    message = _("User(s) ${added} added to group.")
    message.mapping {'added': view.quotify_list(added)}
else:
    message = _("No other users added (were they already in this group?)")

return view.tab_edit(
    message_type="feedback", 
    message=message)

