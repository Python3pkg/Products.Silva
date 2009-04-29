##parameters=userids=None
from Products.Silva.i18n import translate as _

request = context.REQUEST
model = request.model

if not userids:
    return context.tab_edit(
        message_type="error",
        message=_("No users selected, so none added.")
        )

added = []
current_users = model.listUsers()
for userid in userids:
    if not userid in current_users:
        model.addUser(userid)
        added.append(userid)

if added:
    message = _("User(s) ${added} added to group.",
                mapping={'added': context.quotify_list(added)})
else:
    message = _("No other users added (were they already in this group?)")

return context.tab_edit(
    message_type="feedback",
    message=message)

