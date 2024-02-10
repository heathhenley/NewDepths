Backend
- hook up csb endpoint
- switch to real db
- scripts to seed for testing
- something to send emails (resend ?)
- actually send the emails
- get full backend set up and working (probably railway)
  - worker as a cron
  - api as a normal service
- add webhook instead of email as an option for notifications

Frontend
- auth with backend
  - require auth to add bbox, need email for notification
- load map
- add new bbox button (click and drag or click start/stop)
- submit bbox to db
- show users bboxes on map
- show users bboxes in list
- user can delete their own bboxes
- user can edit their own bboxes
- user can edit email
- user can delete account