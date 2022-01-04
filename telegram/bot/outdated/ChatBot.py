import telegram

hermes_token = '5048073346:AAF-MK3hv3K8d5MdR8PgCcukUU3qrEcO3r0'
hermes = telegram.Bot(token = hermes_token)
updates = hermes .getUpdates()
for u in updates:
    print(u.message)