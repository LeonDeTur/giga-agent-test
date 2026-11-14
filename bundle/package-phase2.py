from pathlib import Path
import zipfile,hashlib,json
r=Path('bundle/dpo-giga-agent')
p=r/'README.md';s=p.read_text(encoding='utf-8').replace('в кэши текущего пользователя','в .cache внутри комплекта').replace('Это **образец**, а не результат проверки этой поставки:', 'Это **образец ожидаемых 7/7**: архитектор получил 6/7; строка «Ресурсы пользователя» исправлена после испытания и требует повторной проверки. Остальные шесть строк прошли реальный тест:').replace('Не менее примерно 4 ГБ свободного места','Не менее примерно 5 ГБ свободного места');p.write_text(s,encoding='utf-8')
zpath=Path('bundle/dpo-giga-agent.zip')
with zipfile.ZipFile(zpath,'w',zipfile.ZIP_DEFLATED) as z:
 for p in sorted(r.rglob('*')):
  rel=p.relative_to(r)
  if not p.is_file() or any(x in rel.parts for x in ('.env','.venv','.giga_agent','.cache','tools','.downloads','__pycache__')) or p.suffix in ('.log','.pyc'):continue
  assert str(rel).isascii(),rel
  z.write(p,str(Path(r.name)/rel))
with zipfile.ZipFile(zpath) as z:
 assert z.testzip() is None
 names=z.namelist()
 assert not any('/.env' in n and not n.endswith('.env.example') for n in names)
 Path('bundle/zip-contents.txt').write_text('\n'.join(names),encoding='utf-8')
 print(json.dumps({'files':len(names),'bytes':zpath.stat().st_size,'sha256':hashlib.sha256(zpath.read_bytes()).hexdigest()}))
