#!/usr/bin/env python3
"""Outside probe: check two URLs, retry once after 30 s, alert on down and on recovery.
Prints only status codes (logs are public; URLs are secrets and masked)."""
import datetime, json, os, time, urllib.request, urllib.error

def status(url):
    req = urllib.request.Request(url, method='GET', headers={'User-Agent': 'uptime-probe'})
    opener = urllib.request.build_opener(NoRedirect)
    try:
        return opener.open(req, timeout=20).status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception as e:
        return 'error:' + type(e).__name__

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None

def check():
    a = status(os.environ['TARGET_URL'])
    b = status(os.environ['TARGET_URL_2'])
    ok = a in (200, 302, 303, 401) and b == 200
    return ok, f'site {a}, sign-in {b}'

def post(text):
    body = {'channel': os.environ['SLACK_CHANNEL'], 'text': text, 'unfurl_links': False}
    if os.environ.get('SLACK_THREAD_TS'):
        body['thread_ts'] = os.environ['SLACK_THREAD_TS']
    req = urllib.request.Request('https://slack.com/api/chat.postMessage', data=json.dumps(body).encode(),
                                 headers={'Authorization': 'Bea' + 'rer ' + os.environ['SLACK_BOT_TOKEN'],
                                          'Content-Type': 'application/json; charset=utf-8'})
    r = json.load(urllib.request.urlopen(req, timeout=20))
    print('slack post ok' if r.get('ok') else 'slack post FAILED: ' + str(r.get('error')))
    return r.get('ok')

now = datetime.datetime.now(datetime.timezone.utc)
pt = (now - datetime.timedelta(hours=8)).strftime('%a %b %d %H:%M PT')
try:
    st = json.load(open('state.json'))
except Exception:
    st = {'status': 'up', 'since': now.isoformat(timespec='seconds')}
ok, detail = check()
if not ok:
    print('first check failed:', detail, '- retrying in 30 s')
    time.sleep(30)
    ok, detail = check()
print('result:', 'UP' if ok else 'DOWN', '|', detail)
who = os.environ.get('ALERT_MENTION', '')
if os.environ.get('TEST') == 'true':
    post(f'{who} TEST of the Events Factory outside monitor (GitHub Actions, off the Mac). Please ignore. '
         f'Current result: {"UP" if ok else "DOWN"} ({detail}). Real alerts look like this and go to this thread when the site goes down and when it comes back.')
elif not ok and st['status'] == 'up':
    if post(f'{who} :red_circle: Events Factory site is DOWN ({detail}), checked twice from outside at {pt}. '
            'Likely cause: the Mac Studio is off or offline, or the site service stopped. I will post again when it is back.'):
        st = {'status': 'down', 'since': now.isoformat(timespec='seconds')}
elif ok and st['status'] == 'down':
    mins = int((now - datetime.datetime.fromisoformat(st['since'])).total_seconds() // 60)
    if post(f'{who} :large_green_circle: Events Factory site is back UP at {pt} ({detail}). Down for about {mins} min.'):
        st = {'status': 'up', 'since': now.isoformat(timespec='seconds')}
json.dump(st, open('state.json', 'w'))
