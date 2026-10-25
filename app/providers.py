"""Provider boundaries: one selected brain per turn, shared memory and tools."""
import json
import urllib.request
import urllib.error
from datetime import datetime, timezone

CATALOG={
 'gemini':{'provider':'google','model':'gemini-3.1-pro-preview','label':'Gemini 3.1 Pro','currency':'USD','input_per_million':2.,'output_per_million':12.,'vision':True},
 'deepseek-flash':{'provider':'deepseek','model':'deepseek-v4-flash','label':'DeepSeek V4 Flash · 常规模式','currency':'CNY','input_per_million':3.,'output_per_million':9.,'vision':False},
 'deepseek-pro':{'provider':'deepseek','model':'deepseek-v4-pro','label':'DeepSeek V4 Pro · 常规模式','currency':'CNY','input_per_million':9.,'output_per_million':27.,'vision':False},
}
CATALOG.update({
 'gemini-4-argon':{'provider':'google','model':'gemini-4-argon','label':'Gemini 4 Argon','currency':'USD','input_per_million':2.,'output_per_million':10.,'vision':True,
                    'price_switch_on':'2026-12-01','future_input_per_million':4.,'future_output_per_million':20.,
                    'price_note_promo':'优惠至 2026-11-30；之后输入 $4、输出 $20／百万 token。',
                    'price_note_standard':'已按 2026-12-01 起标准价格估算。',
                    'model_note':'Argon 本版使用 32,768 token 思考与输出总额度；temperature 不适用。额度是上限，不要求写满。',
                    'cache_per_million':.1,'future_cache_per_million':.2,'price_verified_on':'2026-10-18'},
 'gemini-flash':{'provider':'google','model':'gemini-3-flash-preview','label':'Gemini 3 Flash Preview','currency':'USD','input_per_million':.5,'output_per_million':3.,'vision':True},
 'gemini-lite':{'provider':'google','model':'gemini-3.1-flash-lite','label':'Gemini 3.1 Flash-Lite','currency':'USD','input_per_million':.25,'output_per_million':1.5,'vision':True},
 'gemini-35-flash':{'provider':'google','model':'gemini-3.5-flash','label':'Gemini 3.5 Flash','currency':'USD','input_per_million':1.5,'output_per_million':9.,'vision':True},
 'gemini-35-lite':{'provider':'google','model':'gemini-3.5-flash-lite','label':'Gemini 3.5 Flash-Lite','currency':'USD','input_per_million':.3,'output_per_million':2.5,'vision':True},
 'gemini-37-flash':{'provider':'google','model':'gemini-3.7-flash','label':'Gemini 3.7 Flash','currency':'USD','input_per_million':.75,'output_per_million':3.75,'vision':True,
                    'price_switch_on':'2027-01-01','future_input_per_million':1.5,'future_output_per_million':7.5},
})
# Subscription models are not advertised until a separate identity is configured.

def price_day():
    return datetime.now(timezone.utc).date().isoformat()

def selected(cfg):
    key=cfg.get('brain','gemini')
    if key not in CATALOG:raise ValueError('请选择已支持的模型。')
    price=dict(CATALOG[key])
    if price.get('price_switch_on'):
        promo=price_day()<price['price_switch_on']
        if not promo:
            price.update(input_per_million=price['future_input_per_million'],output_per_million=price['future_output_per_million'])
            if 'future_cache_per_million' in price:price['cache_per_million']=price['future_cache_per_million']
        price['price_note']=price.get('price_note_promo','优惠至 2026-12-31；之后输入 $1.50、输出 $7.50／百万 token') if promo else price.get('price_note_standard','已按优惠结束后的标准价格估算')
    if price.get('model_note'):price['price_note']=price.get('price_note','')+price['model_note']
    return price


def generation_config(cfg):
    result={'temperature':cfg['temperature'],'maxOutputTokens':cfg['max_output_tokens'],
            'thinkingConfig':{'thinkingLevel':cfg['thinking_level']}}
    if selected(cfg)['model']=='gemini-4-argon':
        # Official synchronous REST cap, shared by thinking and visible output.
        # No automatic long-decode continuation or extra hidden requests.
        result.pop('temperature')
        result['maxOutputTokens']=32768
    return result

def rmb(input_tokens,output_tokens,cfg):
    return rmb_at_price(input_tokens,output_tokens,selected(cfg),cfg['usd_rmb'])

def rmb_at_price(input_tokens,output_tokens,p,usd_rmb):
    amount=(input_tokens*p['input_per_million']+output_tokens*p['output_per_million'])/1_000_000
    return amount*(usd_rmb if p['currency']=='USD' else 1)

def rmb_usage(usage,price,usd_rmb):
    prompt=usage['promptTokenCount'];output=usage['candidatesTokenCount']+usage.get('thoughtsTokenCount',0)
    cached=usage.get('cachedContentTokenCount')
    if 'cache_per_million' not in price or type(cached) is not int or not 0<=cached<=prompt:
        return rmb_at_price(prompt,output,price,usd_rmb)
    amount=((prompt-cached)*price['input_per_million']+cached*price['cache_per_million']+output*price['output_per_million'])/1_000_000
    return amount*(usd_rmb if price['currency']=='USD' else 1)


def schema(value):
    if isinstance(value,list):return [schema(v) for v in value]
    if isinstance(value,dict):return {k:(v.lower() if k=='type' and isinstance(v,str) else schema(v)) for k,v in value.items()}
    return value

def deepseek_payload(payload,cfg):
    messages=[{'role':'system','content':payload['systemInstruction']['parts'][0]['text']}]
    for c in payload['contents']:
        parts=c['parts']
        native=next((p['_deepseek_message'] for p in parts if '_deepseek_message' in p),None)
        if native is not None:
            messages.append(native);continue
        if any('inlineData' in p for p in parts):raise ValueError('当前接入的 DeepSeek 文本模型不能看图片，请切回 Gemini。')
        tools=[p['functionResponse'] for p in parts if 'functionResponse' in p]
        if tools:
            messages.extend({'role':'tool','tool_call_id':p['id'],'content':json.dumps(p['response'],ensure_ascii=False)} for p in tools)
        text='\n'.join(p['text'] for p in parts if 'text' in p and not p.get('thought'))
        if text:messages.append({'role':'assistant' if c['role']=='model' else 'user','content':text})
    return {'model':selected(cfg)['model'],'messages':messages,'stream':False,
            'thinking':{'type':'disabled'},'temperature':cfg['temperature'],'max_tokens':cfg['max_output_tokens'],
            'tools':[{'type':'function','function':schema(f)} for t in payload.get('tools',[]) for f in t.get('functionDeclarations',[])],
            'tool_choice':'none' if payload.get('toolConfig',{}).get('functionCallingConfig',{}).get('mode')=='NONE' else 'auto'}

def deepseek(payload,cfg,key,no_redirect):
    request=urllib.request.Request('https://api.deepseek.com/chat/completions',
        data=json.dumps(deepseek_payload(payload,cfg),ensure_ascii=False).encode('utf-8'),
        headers={'Content-Type':'application/json','Authorization':'Bearer '+key},method='POST')
    try:
        with urllib.request.build_opener(no_redirect()).open(request,timeout=120) as response:raw=response.read(4_000_001)
        if len(raw)>4_000_000:raise ValueError('response too large')
        return normalize(json.loads(raw))
    except urllib.error.HTTPError as error:
        raise ValueError(f'DeepSeek 返回 HTTP {error.code}；未自动重试，预留费用暂保留待核对。') from None
    except Exception:
        raise ValueError('DeepSeek 请求未完成；未自动重试，预留费用暂保留待核对。') from None

def normalize(data):
    choice=data['choices'][0];message=choice['message'];parts=[]
    if message.get('content'):parts.append({'text':message['content']})
    calls=message.get('tool_calls') or []
    if calls:parts.append({'_deepseek_message':message})
    for call in calls:
        try:args=json.loads(call['function']['arguments'])
        except (TypeError,ValueError):args={}
        parts.append({'functionCall':{'name':call['function']['name'],'id':call['id'],'args':args}})
    original=data.get('usage') or {};usage={'provider':'deepseek','provider_usage':original}
    if 'prompt_tokens' in original:usage['promptTokenCount']=original['prompt_tokens']
    if 'completion_tokens' in original:usage['candidatesTokenCount']=original['completion_tokens']
    return {'usageMetadata':usage,'candidates':[{'content':{'parts':parts},'finishReason':'MAX_TOKENS' if choice.get('finish_reason')=='length' else choice.get('finish_reason','STOP')}]}
