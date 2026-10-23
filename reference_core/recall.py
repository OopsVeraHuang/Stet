"""Lexical recall plus offline semantic fusion across originals and live chat.

No external embedding calls. The model may reformulate queries through a
bounded search_memory tool. Scores are relevance hints, never factual confidence.
"""
import math
import re
import unicodedata
import semantic_memory
import context_policy


def hybrid(api,text,limit=48,exclude_chat=()):
    pool_limit=max(limit,96) if context_policy.date_range(text) else limit
    lexical = retrieve(api,text,pool_limit,exclude_chat)
    if not terms(text):return lexical
    semantic = semantic_candidates(text,semantic_memory.retrieve(api,text,96,exclude_chat))
    return context_policy.date_priority(fuse(lexical,semantic,pool_limit),text)[:limit]


def semantic_candidates(text, rows, limit=24):
    """A bounded wider pool, then combine meaning with rare literal detail.

    Chinese two-character words often disappear from trigram FTS queries after
    a small rephrase. Score them within this pool, without a whole-archive scan.
    No literal overlap (including cross-language recall) leaves cosine order intact.
    """
    query_terms=set(terms(text))
    query_terms.update(run[i:i+2] for run in re.findall(r'[\u3400-\u9fff]+',text)
                       for i in range(len(run)-1) if run[i:i+2] not in STOP)
    query_terms=sorted(query_terms)[:240]
    weights={t:math.log(1+len(rows)/(1+sum(t in p['raw_text'].lower() for p in rows))) for t in query_terms}
    total=sum(weights.values()) or 1
    def script(value):
        counts=[len(re.findall(pattern,value)) for pattern in (r'[\u3400-\u9fff]',r'[a-zA-Z]',r'[\u0400-\u052f]')]
        return counts.index(max(counts)) if max(counts)>sum(counts)*.5 else None
    query_script=script(text)
    ranked=[]
    for p in rows:
        item=dict(p);detail=dict(p.get('retrieval',{}))
        overlap=sum(w for t,w in weights.items() if t in p['raw_text'].lower())/total
        # Incidental Latin acronyms in Chinese prose must not displace genuine
        # cross-language matches. Literal scoring is for the same main script.
        if query_script!=script(p['raw_text']):overlap=0
        detail['literal_coverage']=round(overlap,4)
        detail['rerank_score']=detail.get('score',0)+.4*overlap
        item['retrieval']=detail;ranked.append(item)
    return sorted(ranked,key=lambda p:-p['retrieval']['rerank_score'])[:limit]


def fuse(lexical,semantic,limit=48):
    if not semantic:return lexical
    # Reciprocal-rank fusion avoids pretending BM25 and cosine use the same scale.
    ranked = {}
    for channel,rows in [('lexical',lexical),('semantic',semantic)]:
        for rank,item in enumerate(rows):
            entry = ranked.setdefault(item['id'],{'item':item,'score':0,'channels':[],'details':{}})
            entry['score'] += 1/(20+rank+1)
            entry['channels'].append(channel)
            entry['details'][channel] = item.get('retrieval',{})
    result,seen = [],set()
    for entry in sorted(ranked.values(),key=lambda row:-row['score']):
        item = dict(entry['item'])
        normalized = ' '.join(item['raw_text'].split())
        if normalized in seen:continue
        seen.add(normalized)
        item['retrieval'] = {'method':'hybrid','channels':entry['channels'],
            'score':round(entry['score'],6),'details':entry['details']}
        if entry['details'].get('semantic',{}).get('span'):
            item['retrieval']['span'] = entry['details']['semantic']['span']
        result.append(item)
        if len(result)>=limit:break
    return result


def follows_recent(text, previous):
    """Conservative short-turn continuity hint; model-directed recall remains available."""
    if not previous or len(text)>120 or re.search(r'以前|上次|过去|历史|记得|回忆|哪天|何时|搜索|检索',text):
        return False
    def grams(value):
        return {run[i:i+2] for run in re.findall(r'[\u3400-\u9fff]+',value) for i in range(len(run)-1)}
    overlap=grams(text)&grams(previous)
    return len(overlap)>=3 or (len(overlap)>=2 and bool(re.search(r'什么|怎么|哪个|你说|刚才|这个|那个',text)))

STOP = set('今天 明天 昨天 现在 我们 你们 他们 这个 那个 什么 怎么 为什么 可以 觉得 记得 记忆 自己 一下 已经 还是 时候 事情 然后 但是 就是 真的 知道 一起 助手 助手'.split())
FILLERS = ('你还记得', '你记得', '记不记得', '帮我查一下', '自己检索一下', '助手', 'AGENT', 'USER', '想起来', '有没有', '我想问', '我想去')


def terms(text):
    text = unicodedata.normalize('NFKC', text).lower()[:1800]
    for word in FILLERS:
        text = text.replace(word.lower(), ' ')
    compact = re.sub(r'[\W_]+', '', text)
    if compact in {'你好','您好','你好呀','嗨','嗨嗨','哈喽','早','早安','早上好','早安呀','午安','下午好',
                   '晚上好','晚安','晚安呀','晚安啦','晚安哦','醒醒','醒醒啦','hi','hello','hey','goodmorning','goodnight'}:
        return []  # A greeting needs relationship context, not dozens of near-identical old greetings.
    terms = []
    # Keep Cyrillic and accented Latin words too, not only ASCII English.
    terms.extend(w for w in re.findall(r"[^\W\d_]+(?:[-’'][^\W\d_]+)*",text)
                 if len(w)>1 and not w.isascii() and not re.search(r'[\u3400-\u9fff]',w))
    for run in re.findall(r'[\u3400-\u9fff]+|[a-z0-9][a-z0-9_-]+', text):
        if run in STOP:
            continue
        if re.search('[a-z0-9]', run):
            if run not in {'the', 'and', 'you', 'that', 'this', 'have', 'with', 'what', 'was', 'for'}:
                terms.append(run)
        elif len(run) >= 3:
            terms.extend(run[i:i+3] for i in range(len(run)-2)
                         if run[i:i+2] not in STOP and run[i+1:i+3] not in STOP)
        elif len(run) == 2 and run not in STOP:
            terms.append(run)
    return list(dict.fromkeys(terms))[:80]


def candidates(db, table, id_column, text_column, query_terms, exclude_ids=()):
    long = [t for t in query_terms if len(t) >= 3]
    rows = []
    # Identifiers are fixed internal constants from the caller; all query data is bound.
    if long:
        expression = ' OR '.join('"'+t.replace('"','""')+'"' for t in long)
        rows = db.execute(f'SELECT {id_column} AS id,{text_column} AS text,bm25({table}) AS rank FROM {table} WHERE {text_column} MATCH ? ORDER BY rank LIMIT 80', (expression,)).fetchall()
    if not rows:
        short = [t for t in query_terms if len(t) == 2][:6]
        if short:
            where = ' OR '.join(f'instr({text_column},?)>0' for _ in short)
            rows = db.execute(f'SELECT {id_column} AS id,{text_column} AS text,0 AS rank FROM {table} WHERE {where} LIMIT 80', short).fetchall()
    if not rows:
        return []
    # Rarity is measured in the candidate set; BM25 remains a stable tie-breaker.
    df = {t: sum(t in r['text'].lower() for r in rows) for t in query_terms}
    results = []
    excluded = set(str(i) for i in exclude_ids)
    for order, row in enumerate(rows):
        if str(row['id']) in excluded:
            continue
        matches = [t for t in query_terms if t in row['text'].lower()]
        score = sum(1 + math.log((len(rows)+1)/(df[t]+1)) for t in matches)
        if score:
            results.append({'id': row['id'], 'score': score, 'order': order, 'matches': matches})
    return sorted(results, key=lambda p: (-p['score'], p['order']))


def retrieve(api, text, limit=48, exclude_chat=()):
    query_terms = terms(text)
    if not query_terms:
        return []
    with api.archive() as db:
        old = candidates(db, 'paragraph_search', 'paragraph_id', 'raw_text', query_terms)
        branches=candidates(db,'gpt_aux_search','node_uid','raw_text',query_terms)
        for hit in branches:
            row=db.execute('SELECT status FROM gpt_nodes WHERE id=?',(hit['id'],)).fetchone()
            if row and row[0]=='alternate_dialogue':old.append(dict(hit,id='gptaux:'+hit['id']))
    with api.state_db() as db:
        live = candidates(db, 'chat_search', 'chat_id', 'raw_text', query_terms, exclude_chat)
        study = candidates(db, 'study_search', 'note_id', 'raw_text', query_terms)
        old.extend(dict(hit,id='study:'+str(hit['id'])) for hit in study)
    hits = [(r, False) for r in old] + [(r, True) for r in live]
    hits.sort(key=lambda h: (-h[0]['score'], h[0]['order']))
    result, groups, texts = [], set(), set()
    # Relative lexical score, not calibrated semantic confidence. Do not pad to a quota.
    cutoff = hits[0][0]['score'] * .55 if hits else 0
    for hit, is_live in hits:
        if hit['score'] < cutoff:
            break
        pid = 'chat:'+str(hit['id']) if is_live else hit['id']
        try:item = api.get_paragraph(pid)
        except ValueError:continue  # A note can be withdrawn between selection and hydration.
        # Avoid spending every slot on adjacent paragraphs from the same exchange.
        group = (item['source_id'], item['number']//4)
        normalized = ' '.join(item['raw_text'].split())
        if group in groups or normalized in texts:
            continue
        groups.add(group)
        texts.add(normalized)
        item['retrieval'] = {'method': 'local_lexical', 'matched_terms': hit['matches'], 'score': round(hit['score'], 3)}
        result.append(item)
        if len(result) >= limit:
            break
    return result
