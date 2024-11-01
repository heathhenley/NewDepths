Backend
- dry out fetchers more
  - they are all basically the same with different urls, different time
    attributes (ARRIVAL_DATE, etc), and slightly different return attributes
    (PLATFORM, DOWNLOAD_URL, etc) - so they just need to be parameterized a bit
- dry out checking for hx-request / cache headers stuff
- set up db backups
- set up db migrations (alembic?)
- should bboxes have names / descriptions?
- figure out query with since date included
  - reduce bandwidth usage
  - more useful in the webhook case probably
  - it just needs to be manually added, if the '>' in the query gets url
    encoded it breaks the query
- probably need email verification to avoid spam
- add webhook instead of email as an option for notifications
- style everything better, make it look nice
- add password rules and validation on client and server
- configurable notification settings?
  - email vs webhook
  - frequency (max once per day, once per week, etc)
  - only mbes, only csb, both, etc
- support multiple emails per user / multiple webhooks per user
  - configure boxes to notify different emails/webhooks
  - configure boxes to only apply to certain data
- handler for sns notifications
  - get notification, figure out who cares about it, queue up the email
    or webhook
- refactor in to use cases, right now it's all mixed with request handling / 
  response handling
  - use cases should be the only thing that touches the db
  - they use the crud tools that are already there

Frontend
- show users existing bboxes on map ? 
- user can edit email
- user can delete account
- user can change password
- switch to esri web map? they have some controls and stuff already implemented
  as 'widgets' - might be nicer
- if the orders stay in 'initialized' for more than X (maybe a couple hours or so) they are probably failed and should be updated to show that (the point store api doesn't really say atm)
