from mongoengine import Document, StringField, DateTimeField, ListField, DictField, connect,IntField
from datetime import datetime
import tldextract,requests
from pymongo import MongoClient
import os,json,sys,re
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config import config
def current_time():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
connect(db='watch', host='mongodb://127.0.0.1:27017/watch')

def get_domain_name(url):
    extracted = tldextract.extract(url)
    if extracted.domain and extracted.suffix:
        return f"{extracted.domain}.{extracted.suffix}"
    return url
class Programs(Document):
    program_name = StringField(required=True)
    scopes = ListField(StringField(), default=[])
    ooscopes = ListField(StringField(), default=[])
    providers = ListField(StringField(), default=[])
    config = DictField()
    created_date = DateTimeField(default=datetime.now)

    meta = {
        'indexes': [
            {'fields': ['program_name'], 'unique': True} 
        ]
    }
class Subdomains(Document):
    program_name = StringField(required=True)
    subdomain = StringField(required=True)
    scope = StringField(required=True)
    providers = ListField(StringField())
    created_date = DateTimeField(default=datetime.now)
    last_update = DateTimeField(default=datetime.now)

    meta = {
        'indexes': [
            {'fields': ['program_name', 'subdomain'], 'unique': True}  
        ]
    }
class LiveSubdomains(Document):
    program_name = StringField(required=True)
    subdomain = StringField(required=True)
    scope = StringField(required=True)
    ips = ListField(StringField())
    info = StringField()
    created_date = DateTimeField(default=datetime.now())
    last_update = DateTimeField(default=datetime.now())
    meta = {
        'indexes': [
            {'fields': ['program_name', 'subdomain'], 'unique': True}
        ]
    }

class http(Document):
     program_name = StringField(required=True)
     subdomain = StringField(required=True)
     scope = StringField(required=True)
     ips = ListField(StringField())
     tech = ListField(StringField())
     title = StringField()
     status_code = IntField()
     headers = DictField()
     url = StringField()
     final_url = StringField()
     favicon = StringField()
     info = StringField()
     created_date = DateTimeField(default=datetime.now())
     last_update = DateTimeField(default=datetime.now())

     meta = {         
        'indexes': [
           {'fields': ['program_name', 'subdomain'], 'unique': True}
       ]
     }
# def notify_tel(message: str):
#     data = {
#         'chat_id': 1956879076,
#         'text': message
#     }

#     response = requests.post(config().get("TELEGRAM_BOT_URL"), data=data)
#     if response.status_code == 200:
#         print("Message sent successfully!")
#     else:
#         print(f"Failed to send message. Status code: {response.status_code}")


connect(db="watch" , host="mongodb://127.0.0.1:27017/watch")

def upsert_http(obj):
    program = Programs.objects(scopes__contains=obj.get("scope")).first()
    if not program:
        print(f"[{current_time()}] No program found for scope: {obj.get('scope')}")
        return
    if obj.get('status_code') == 403 and  "fareharbor.com" == obj.get('scope'):
     print(f"[!] Skipping domain due to 403: {obj.get('scope')} (status: 403)")
     return

    subdomain = obj.get("subdomain")
    existing = http.objects(subdomain=subdomain).first()

    if existing:
        title_old = existing.title
        title_new = obj.get('title')
        if title_old != title_new:
            #notify_tel(f"'{subdomain}' title changed from '{title_old}' to '{title_new}'!")
            existing.title = title_new
            print(f"[{current_time()}] Changed title for: {subdomain}")

        status_old = existing.status_code
        status_new = obj.get('status_code')
        if status_old != status_new:
            #notify_tel(f"'{subdomain}' status_code changed from '{status_old}' to '{status_new}'!")
            existing.status_code = status_new
            print(f"[{current_time()}] Changed status_code for: {subdomain}")

        favicon_old = existing.favicon
        favicon_new = obj.get('favicon')
        if favicon_old != favicon_new:
            #notify_tel(f"'{subdomain}' favicon changed from '{favicon_old}' to '{favicon_new}'!")
            existing.favicon = favicon_new
            print(f"[{current_time()}] Changed favicon for: {subdomain}")

        existing.ips = obj.get('ips')
        tech_raw = obj.get('tech', [])
        existing.tech = tech_raw if isinstance(tech_raw, list) else [tech_raw]
        existing.headers = obj.get('headers')
        existing.url = obj.get('url')
        existing.final_url = obj.get('final_url')
        existing.last_update = datetime.now()
        existing.save()

    else:
        tech_raw = obj.get('tech', [])
        tech = tech_raw if isinstance(tech_raw, list) else [tech_raw]
        new_http = http(
            program_name = program.program_name,
            subdomain = subdomain,
            scope = obj.get('scope'),
            ips = obj.get('ips'),
            tech = tech,
            title = obj.get('title'),
            status_code = obj.get('status_code'),
            headers = obj.get('headers'),
            url = obj.get('url'),
            final_url = obj.get('final_url'),
            favicon = obj.get('favicon'),
            created_date = datetime.now(),
            last_update = datetime.now(),
        )
        new_http.save()
        #notify_tel(f"'{subdomain}' Fresh HTTP service for '{program_name}' program!")
        print(f"[{current_time()}] Inserted new HTTP service: {subdomain}")

def upsert_lives(obj):
    
    if not obj.get("ips"):
        return

    program = Programs.objects(scopes=obj.get("domain")).first()
    existing = LiveSubdomains.objects(subdomain=obj.get("subdomain")).first()
    if existing:
        existing.ips.sort()
        obj.get("ips").sort()
        if obj.get("ips") != existing.ips:
            existing.ips = obj.get("ips")
            
            print(f"[{current_time()}] Updated live subdomain: {obj.get("subdomain")}")
        existing.last_update = datetime.now()
        existing.save()
    else:
        new_live_subdomain = LiveSubdomains(
            program_name=program.program_name,
            subdomain=obj.get("subdomain"),
            scope=obj.get("domain"),
            ips=obj.get("ips"),
            info=obj.get("info"),
            created_date=datetime.now(),
            last_update=datetime.now()
        )
        new_live_subdomain.save()

        #notify_tel(f"'{obj.get("subdomain")}' Fresh sub for '{obj.get("program.program_name")}' program!")

        print(f"[{current_time()}]Inserted new subdomain: {obj.get("subdomain")}")
        
def upsert_program(program_name, new_scopes, new_ooscopes, new_providers):
    program = Programs.objects(program_name=program_name).first()

    existing_scopes = []
    existing_ooscopes = []
    existing_providers = []

    if program:
        existing_scopes = program.scopes or []
        existing_ooscopes = program.ooscopes or []
        existing_providers = program.providers or []

    combined_scopes = list(set(existing_scopes) | set(new_scopes))
    combined_ooscopes = list(set(existing_ooscopes) | set(new_ooscopes))
    combined_providers = list(set(existing_providers) | set(new_providers))

    if program:
        program.scopes = combined_scopes
        program.ooscopes = combined_ooscopes
        program.providers = combined_providers
        program.save()
        print(f"[{current_time()}] Synced program: {program.program_name}")
    else:
        new_prog = Programs(
            program_name=program_name,
            created_date=datetime.now(),
            scopes=combined_scopes,
            ooscopes=combined_ooscopes,
            providers=combined_providers
        )
        new_prog.save()
        print(f"[{current_time()}] Inserted new live program: {new_prog.program_name}")

def upsert_subdomain(program_name, subdomain_name, provider):
    banned_patterns = [
        r'^[a-f0-9\-]{5,}--[^.]+\.(netlify\.com)$',
        r'^\d+(\.\d+)*\.(netlify\.com)$',
        r'^[a-z0-9\-]{10,}\.(netlify\.com)$',
        r'^[a-z0-9\-]+\.(hubspot(email|pagebuilder)\.(net|com|eu))$',
        r'^[a-z0-9\-]+\.(performable\.com)$'
    ]
    for pattern in banned_patterns:
        if re.match(pattern, subdomain_name, re.IGNORECASE):
            return True

    program = Programs.objects(program_name=program_name).first()
    if not program:
        return True

    if subdomain_name in program.ooscopes:
        return True

    is_in_program_scope = False
    for allowed_scope in program.scopes:
        if subdomain_name == allowed_scope or subdomain_name.endswith(f".{allowed_scope}"):
            is_in_program_scope = True
            break

    if not is_in_program_scope:
        return True

    existing = Subdomains.objects(program_name=program_name, subdomain=subdomain_name).first()
    if existing:
        if provider not in existing.providers:
            existing.providers.append(provider)
            existing.last_update = datetime.now()
            existing.save()
    else:
        new_subdomain = Subdomains(
            program_name=program_name,
            subdomain=subdomain_name,
            scope=get_domain_name(subdomain_name),
            providers=[provider],
            created_date=datetime.now(),
            last_update=datetime.now()
        )
        new_subdomain.save()
    return False
