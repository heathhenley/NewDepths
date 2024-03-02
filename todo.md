Backend
- maybe add some limits?
  - how many bboxes can a user have? - maybe like 5?
    - just add a check and return an error if they try to add more server side
  - how much area can a bbox cover?
- figure out query with since date included
  - reduce bandwidth usage
  - more useful in the webhook case probably
  - it just needs to be manually added, if the '>' in the query gets url
    encoded it breaks the query
- make sure jinja is set up to autoescape html (I think it isn't the default)
- probably need email verification to avoid spam
- add webhook instead of email as an option for notifications
- style everything better, make it look nice
- add password rules and validation on client and server
- configurable notification settings?
  - email vs webhook
  - frequency (max once per day, once per week, etc)
  - only mbes, only csb, both, etc

Frontend
- log in form is not centered correctly when the page is large
- show users existing bboxes on map ? 
- show users existing bboxes in list ? 
- user can delete their own bboxes ?
- user can edit email
- user can delete account
- switch to esri web map? they have some controls and stuff already implemented
  as 'widgets' - but be nicer
