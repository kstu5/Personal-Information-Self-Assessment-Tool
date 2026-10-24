"""Check a launched console-free app without modifying the visible draft."""
import html
import json
import re
import sys
import urllib.request

url=sys.argv[1]
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
source=opener.open(url,timeout=5).read().decode()
boot=json.loads(html.unescape(re.search(r'<meta name="app-boot" content="([^"]+)"',source).group(1)))
request=urllib.request.Request(url+'/api/check',data=json.dumps({'title':'','body':'전화: 010-0000-0000','revision':1}).encode(),headers={'Content-Type':'application/json','X-App-Token':boot['token'],'Origin':url},method='POST')
result=json.loads(opener.open(request,timeout=90).read())
assert boot['desktop'] is True
assert any(c['label']=='PHONE' for c in result['candidates'])
assert 'A 모델' in result['engine']
print('Console-free Windows app and its spawned detector are working.')
