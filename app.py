
from flask import Flask, request, jsonify
import sys, os, subprocess
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'database')))
from db import *
from datetime import datetime,timedelta


app = Flask(__name__)

@app.route('/api/subdomains/domain/<domain>')
def subdomains_of_domain(domain):   
    subs = Subdomains.objects(scope=domain)
    if subs:
     sub_list = [s.subdomain for s in subs]
     return jsonify(sub_list)

    else:
     return "domain is not found!"

@app.route('/api/subdomains/program/<p_name>')
def subdomains_of_program(p_name):   
    subs = Subdomains.objects(program_name=p_name)
    if subs:
     sub_list = [s.subdomain for s in subs]
     return jsonify(sub_list)
    else:
     return "domain is not found!" 
@app.route('/api/subdomains/all')
def all_subdomains():   
    subs = Subdomains.objects().all()
    if subs:
     sub_list = [s.subdomain for s in subs]
     return jsonify(sub_list)

    else:
     return "domain is not found!"

@app.route('/api/programs/all')
def all_programs():
    programs = Programs.objects.all()
    response = {}
    for program in programs:
        response[program.program_name] = {
            "scopes" : program.scopes,
            "ooscopes" : program.ooscopes,
            "config" : program.config,
            "created_date" : program.created_date
        }

    print(response)
    return  response
@app.route('/api/lives/all')
def all_lives():   
    twenty_four_hours_ago = datetime.now() - timedelta(hours=48)

    live_subs = LiveSubdomains.objects(last_update__gte=twenty_four_hours_ago).all()
    response = ""
    for live_sub in live_subs:
        response += f"{live_sub.subdomain}\n"
    return response

@app.route('/api/lives/fresh')
def all_lives_fresh():
    twenty_four_hours_ago = datetime.now() - timedelta(hours=12)
    fresh_lives = LiveSubdomains.objects(created_date__gte=twenty_four_hours_ago)
    res_array = [f"{fresh_live.subdomain}" for fresh_live in fresh_lives]
    return '\n'.join(res_array)

@app.route('/api/live/subdomain/<live>')
def all_live_single(live):
    live_obj = LiveSubdomains.objects(subdomain=live).first()
    subdomain_obj = Subdomains.objects(subdomain=live).first()

    if live_obj and subdomain_obj:
        return {
            "program_name": live_obj.program_name,
            "subdomain": live_obj.subdomain,
            "scope": live_obj.scope,
            "ips": live_obj.ips or [],
            "cdn": live_obj.cdn,
            "providers": subdomain_obj.providers or [],
            "created_date": (
                live_obj.created_date.isoformat()
                if live_obj.created_date
                else None
            ),
            "last_update": (
                live_obj.last_update.isoformat()
                if live_obj.last_update
                else None
            )
        }
    return f"{live} not found!"

@app.route('/api/lives/provider/<provider>')
def all_lives_provider(provider):
    twenty_four_hours_ago = datetime.now() - timedelta(hours=24)

    subs = Subdomains.objects(providers__contains=provider)
    subdomain_names = [sub.subdomain.lower() for sub in subs]  
    live_subs = LiveSubdomains.objects(subdomain__in=subdomain_names,last_update__gte=twenty_four_hours_ago)
    live_names = set([l.subdomain.lower() for l in live_subs])
    
    result = [sub.subdomain for sub in subs if sub.subdomain.lower() in live_names]
    return jsonify(result)


@app.route('/api/http/fresh')
def all_http_fresh():
    twenty_four_hours_ago = datetime.now() - timedelta(hours=24)
    fresh_https = http.objects(created_date__gte=twenty_four_hours_ago)

    res_array = [f"{fresh_http.url}" for fresh_http in fresh_https]

    return '\n'.join(res_array)

@app.route('/api/http/provider/<provider>')
def all_http_provider(provider):
    twenty_four_hours_ago = datetime.now() - timedelta(hours=24)

    subs = Subdomains.objects(providers=[provider])
    response = ""
    for sub in subs :
     http_subs = http.objects(subdomain=sub.subdomain ,last_update__gte=twenty_four_hours_ago).first()
     if http:
        response += f"{http.url}\n"

    return jsonify(response)

@app.route('/api/http/all')
def all_http():   
    http_subs = http.objects().all()
    response = ""
    for http_sub in http_subs:
        response += f"{http_sub.subdomain}\n"
    return response



if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
