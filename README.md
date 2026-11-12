# Ensonho

Portal inmobiliario de vivendas xaponesas orientado principalmente ao público español.

## Estrutura

- `backend/`: API FastAPI e importación controlada desde Instagram Graph API.
- `frontend/`: frontend Next.js con renderizado de servidor.
- `database/schema.sql`: esquema de PostgreSQL para Supabase, baseado no UML.
- `tests/`: probas unitarias da API.

O backend usa SQLite por defecto en `backend/data/ensonho.db`, polo que pode
arrincar sen servizos externos. Para Supabase/PostgreSQL, executa
`database/schema.sql` no SQL Editor do proxecto Supabase e define `DATABASE_URL`
no ficheiro `.env`. O schema vincula os perfís con `auth.users` e crea o perfil
tras un rexistro ou inicio con Google. A configuración do provedor Google
realízase en Supabase Auth, non na base de datos. A ruta `GET /api/v1/auth/me`
valida tokens Bearer asinados co `SUPABASE_JWT_SECRET`.

O proxecto Supabase de Ensonho está creado en `West EU (Ireland)` co plan Free.
`SUPABASE_URL`, `SUPABASE_PROJECT_REF` e o host do pooler están no `.env.example`.
Cando `SUPABASE_DB_PASSWORD` estea cuberto no `.env` local, o backend conectará
por TLS ao pooler de sesión de PostgreSQL; a URL constrúese separadamente para
non ter que escapar caracteres do contrasinal. Se queda baleiro, seguirá usando
SQLite. Non gardes o contrasinal da base nin a chave JWT no repositorio.

Para conservar as imaxes das importacións de Instagram, crea en Supabase Storage
un bucket privado chamado `instagram-import-media` e configura
`SUPABASE_SERVICE_ROLE_KEY` só no `backend/.env` local ou no xestor de segredos
do servidor. O backend descarga imaxes e miniaturas dos CDNs de Meta, gárdaas no
bucket e entrega URLs asinadas temporais; non poñas esa chave no frontend nin no
repositorio. As filas de `listing_import_media` relaciónanse co borrador de
`listing_imports` e poderanse asociar á vivenda cando se aprobe.

Para activar a conexión local, introduce o contrasinal PostgreSQL en
`backend/.env` na variable `SUPABASE_DB_PASSWORD`; non o escribas no terminal
que compartes nin no chat. A conexión usa o usuario `postgres.<project-ref>` e
o pooler de sesión de Supabase na porta 5432.

O modelo inclúe perfís e roles, catálogos de oferta e tipo de vivenda, vivendas,
estancias, medios e rexistros de importación con revisión pendente. A localización
gárdase como texto; latitude e lonxitude non se almacenan nesta versión.

`house_types` distingue casa independente (`一戸建て`), unidade nun edificio de
vivendas (`共同住宅`), casa adosada (`長屋建て`) e outros tipos. `Akiya` non é
un tipo de casa: indica que está baleira e debería ser un dato de ocupación
separado. `Machiya` e `kominka` describen estilos/tradicións que poden coincidir
con varias formas físicas, así que convén modelalos como etiquetas ou estilos
nunha evolución posterior. A modalidade de venda/aluguer vai en `offer_types`.

`room_types` contén 32 espazos e denominacións de planos xaponeses, entre eles
`washitsu`, `genkan`, `oshiire` e `DK/LDK`. Estes dous últimos son espazos
combinados; non se deberían duplicar como cociña, comedor e sala separados na
mesma planta. `1R/Studio` é unha denominación do plano completo, non dunha
estancia individual, e pode separarse a un futuro campo de distribución.

Crear anuncios en `POST /api/v1/listings` require un token con rol
`authenticated`, `owner` ou `admin`. O `owner_id` gárdase a partir do `sub` do
token. Se xa existía unha SQLite local anterior a este campo, os anuncios
previos reciben o propietario técnico `legacy` durante a migración automática.

## Arranque local

### API

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

A API estará dispoñible en `http://127.0.0.1:8000`. A documentación interactiva está en `/docs`.

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

O frontend estará dispoñible en `http://localhost:3000`.

## Variables de contorno

Copia `.env.example` a `.env` no backend. Para importar publicacións reais é necesario configurar un token válido de Instagram Graph API. O scaffold non fai scraping de Instagram.

## Próximos pasos

1. Configurar Supabase/PostgreSQL e executar `database/schema.sql`.
2. Engadir autenticación e políticas RLS.
3. Conectar a importación coa API Graph e gardar os borradores na base de datos.
4. Engadir busca, mapas, POI, calendario e reservas.
