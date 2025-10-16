
1. Create a Python 3.11 venv and install requirements:

   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt

2. Create a .env file next to `manage.py` with:

   SECRET_KEY=replace-me
   DJANGO_DEBUG=1
   SLACK_CLIENT_ID=your-slack-client-id
   SLACK_CLIENT_SECRET=your-slack-client-secret
   and some more...

3. Run migrations and start the server:

   python manage.py migrate
   python manage.py runserver


Notes on email restriction
The app checks the email returned by Slack and only allows addresses ending with `@media.ucla.edu`.
This enforces that users must have Slack accounts with Daily Bruin emails.

Docker (build and run)

Or with docker-compose:
docker-compose up --build
