import pathlib, re, collections, math, json, sys
CSS = pathlib.Path('static/css')
VELHOS = ['tokens.css','theme.css','03-theme-dark.css']
FONTES = VELHOS + ['00-palette.css']

decl = {'light':{}, 'dark':{}}
for nome in FONTES:
    p = CSS/nome
    if not p.exists(): continue
    for m in re.finditer(r'([^{}]+)\{([^{}]*)\}', p.read_text(encoding='utf-8'), re.S):
        sel = m.group(1).strip().split('\n')[-1].strip()
        if not (sel.startswith(':root') or 'data-theme' in sel): continue
        ctx = 'dark' if 'data-theme="dark"' in sel else 'light'
        for d in re.finditer(r'(--[a-z0-9-]+)\s*:\s*([^;]+);', m.group(2)):
            decl[ctx][d.group(1)] = d.group(2).strip()

def resolver(tok, ctx, vistos=None):
    vistos = vistos or set()
    if tok in vistos: return ''
    vistos.add(tok)
    v = decl[ctx].get(tok) or decl['light'].get(tok)
    if v is None: return ''
    m = re.fullmatch(r'var\(\s*(--[a-z0-9-]+)\s*\)', v.strip())
    return resolver(m.group(1), ctx, vistos) if m else v.strip()

refs = collections.Counter(); arquivos = collections.defaultdict(set)
ALVOS = []
for base, ext in ((CSS,'.css'), (pathlib.Path('templates'),'.html'), (pathlib.Path('static/js'),'.js')):
    for f in base.rglob('*'):
        if not f.is_file() or f.suffix != ext or f.name in FONTES+['shell.bundle.css','01-tokens.css']: continue
        ALVOS.append(f)
        for m in re.finditer(r'var\(\s*(--[a-z0-9-]+)', f.read_text(errors='replace')):
            refs[m.group(1)] += 1

# --- canonicos -------------------------------------------------------------
PALETA = {'--cv-surface-page':('#eceef1','#0d0f11'), '--cv-surface-card':('#ffffff','#191c1f'),
          '--cv-surface-block':('#eceef1','#23272b'), '--color-accent':('#155b9a','#d8a21b')}
INK = {'--cv-ink':1.0, '--cv-ink-body':0.88, '--cv-ink-muted':0.62, '--cv-ink-soft':0.44}
BORDA = {'--cv-border-soft':0.08, '--cv-border':0.14, '--cv-border-strong':0.26}
RAIO = {'--cv-r-0':0,'--cv-r-sm':8,'--cv-r-md':14,'--cv-r-lg':20,'--cv-r-xl':28,'--cv-r-pill':999}
ESPACO = {'--cv-sp-1':4,'--cv-sp-2':8,'--cv-sp-3':12,'--cv-sp-4':16,'--cv-sp-5':20,'--cv-sp-6':24,'--cv-sp-7':32,'--cv-sp-8':48}
FS = {'--cv-fs-xs':12,'--cv-fs-sm':14,'--cv-fs-md':16,'--cv-fs-lg':20,'--cv-fs-xl':26}
FW = {'--cv-fw-normal':400,'--cv-fw-medium':560,'--cv-fw-bold':700}
MED = {'--cv-h-control-sm':36,'--cv-h-control':48,'--cv-w-page':1280}
SOMBRA = ['--cv-sh-none','--cv-sh-sm','--cv-sh-md','--cv-sh-lg']
Z = {'--cv-z-base':1,'--cv-z-sticky':100,'--cv-z-dropdown':500,'--cv-z-overlay':1000,'--cv-z-toast':2000}

def hex2lab(h):
    h=h.lstrip('#')
    if len(h)==3: h=''.join(c*2 for c in h)
    if len(h)!=6: return None
    try: r,g,b=[int(h[i:i+2],16) for i in (0,2,4)]
    except ValueError: return None
    def lin(v):
        v/=255; return v/12.92 if v<=0.03928 else ((v+0.055)/1.055)**2.4
    r,g,b=lin(r),lin(g),lin(b)
    X=(0.4124*r+0.3576*g+0.1805*b)/0.95047; Y=0.2126*r+0.7152*g+0.0722*b
    Z_=(0.0193*r+0.1192*g+0.9505*b)/1.08883
    f=lambda t: t**(1/3) if t>0.008856 else 7.787*t+16/116
    fx,fy,fz=f(X),f(Y),f(Z_); return (116*fy-16,500*(fx-fy),200*(fy-fz))
def dE(a,b):
    A,B=hex2lab(a),hex2lab(b)
    if not A or not B: return 999
    return math.sqrt(sum((A[i]-B[i])**2 for i in range(3)))
def mix(a,b,p):
    A=hex2lab and None
    ha,hb=a.lstrip('#'),b.lstrip('#')
    if len(ha)==3: ha=''.join(c*2 for c in ha)
    if len(hb)==3: hb=''.join(c*2 for c in hb)
    try:
        A=[int(ha[i:i+2],16) for i in (0,2,4)]; B=[int(hb[i:i+2],16) for i in (0,2,4)]
    except ValueError: return None
    return '#%02x%02x%02x'%tuple(round(A[i]*p+B[i]*(1-p)) for i in range(3))

def familia(t):
    for k,f in [('radius','raio'),('space','espaco'),('gap','espaco'),('padding','espaco'),('margin','espaco'),
      ('font-size','fs'),('font-weight','fw'),('shadow','sombra'),('glow','sombra'),
      ('border','borda'),('height','med'),('width','med'),('z-index','z'),('transition','motion'),
      ('duration','motion')]:
        if k in t: return f
    return 'cor'
def num(v):
    m=re.match(r'^(-?[\d.]+)px$', v.strip()) or re.match(r'^(-?[\d.]+)$', v.strip())
    return float(m.group(1)) if m else None
def maisproximo(alvo, tabela):
    return min(tabela.items(), key=lambda kv: abs(kv[1]-alvo))[0]

INK_L, INK_D = '#0c1420', '#eef3fa'
mapa={}; naomap=[]
for t in sorted({x for x in set(decl['light'])|set(decl['dark']) if refs[x]>0}):
    if t in PALETA or t.startswith('--cv-surface') or t in ('--on-accent','--accent-tint'): continue
    L,D = resolver(t,'light'), resolver(t,'dark')
    fam = familia(t)
    if fam=='raio':
        n=num(L); mapa[t]=maisproximo(n,RAIO) if n is not None else '--cv-r-md'
    elif fam=='espaco':
        n=num(L); mapa[t]=maisproximo(n,ESPACO) if n is not None else None
    elif fam=='fs':
        n=num(L); mapa[t]=maisproximo(n,FS) if n is not None else None
    elif fam=='fw':
        n=num(L); mapa[t]=maisproximo(n,FW) if n is not None else None
    elif fam=='med':
        n=num(L); mapa[t]=maisproximo(n,MED) if n is not None else None
    elif fam=='z':
        n=num(L); mapa[t]=maisproximo(n,Z) if n is not None else None
    elif fam=='motion':
        mapa[t]='--cv-t-fast' if ('1' in L[:3] or '0.1' in L) else '--cv-t-base'
    elif fam=='sombra':
        if not L or L=='none': mapa[t]='--cv-sh-none'
        else:
            blur=re.findall(r'(\d+)px', L); b=max((int(x) for x in blur), default=8)
            mapa[t]='--cv-sh-sm' if b<=4 else ('--cv-sh-md' if b<=20 else '--cv-sh-lg')
    else:
        base = L if L.startswith('#') else ''
        if not base: naomap.append((t,L,D)); continue
        cands={}
        for nome,(cl,_) in PALETA.items(): cands[nome]=dE(base,cl)
        for nome,p in INK.items():
            c=mix(INK_L,'#ffffff',p);  cands[nome]=dE(base,c) if c else 999
        for nome,p in BORDA.items():
            c=mix(INK_L,'#ffffff',p);  cands[nome]=dE(base,c) if c else 999
        for nome,v in (('--cv-danger','#b42318'),('--cv-success','#16805a'),('--cv-warning','#b0790a')):
            cands[nome]=dE(base,v)
        if fam=='borda':
            cands={k:v for k,v in cands.items() if 'border' in k} or cands
        melhor=min(cands.items(), key=lambda kv: kv[1])
        mapa[t]= melhor[0] if melhor[1] < 22 else None
        if mapa[t] is None: naomap.append((t,L,D))
mapa={k:v for k,v in mapa.items() if v}
print(f"MAPEADOS: {len(mapa)}   SEM MAPA: {len(naomap)}")
print("\n=== sem mapa (top 25 por uso) ===")
for t,L,D in sorted(naomap, key=lambda x:-refs[x[0]])[:25]:
    print(f"  {refs[t]:4d}x {t:38} claro={L[:30]:32} escuro={D[:24]}")
json.dump({'mapa':mapa,'naomap':[t for t,_,_ in naomap],'refs':dict(refs)},
          open('/tmp/claude-0/-home-user-gerenciador-de-viagens/eb1c8d22-55f4-5318-ab92-e58595b24529/scratchpad/mapa.json','w'))
