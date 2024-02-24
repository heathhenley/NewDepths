Backend
- hook up csb endpoint
  - the return attributes are a little different, still need to filter on time
  - hopefully it also allows SRID 4326 for the bbox?
- get full backend set up and working (probably railway)
  - worker as a cron
- make sure jinja is set up to autoescape html (I think it isn't the default)
- abstract things for emails, webhooks, and hitting the different endpoints
  so it's less hacked in / coupled + easier to change and extend
- probably need email verification to avoid spam
- check cookies are set up to prevent XSS for the barebones frontend 
  implementation (there's info in htmx docs)
  - do I need an explicit csrf token?
- add simple rate limiting
- add webhook instead of email as an option for notifications
- style everything better, make it look nice
- add password rules and validation on client and server

Frontend
- show users existing bboxes on map ? 
- show users existing bboxes in list ? 
- user can delete their own bboxes ?
- user can edit email
- user can delete account