##parameters=userids=None
model = context.REQUEST.model
view = context

if userids is None:
    return view.lookup_ui(
        message_type="error", message="No users removed.")

selection = view.lookup_get_selection()
for userid in userids:
    if selection.has_key(userid): 
        del selection[userid]

return view.lookup_ui(
    message_type="feedback", 
    message="Users removed from selection.")
