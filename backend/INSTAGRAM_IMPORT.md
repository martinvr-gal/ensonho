# Importación de Casas dende Instagram - Ensonho

## Resumo da Importación

A importación de posts de Instagram foi **completada con éxito**:

### Estatísticas Finais

```
Total de posts importados:    50
Total de imaxes descargadas:  576
Contas de Instagram:          5
Posts por conta:              10

Breakdown:
- @micasajapon:              10 posts, 138 imaxes
- @oldhousesjapan:           10 posts,  95 imaxes
- @omoroiosaka:              10 posts,  99 imaxes
- @japanhousedeal:           10 posts,  89 imaxes
- @akiyajourney.japan:       10 posts, 155 imaxes
```

### Estado dos Datos

- **Base de datos**: PostgreSQL en Supabase
  - 50 registros en `listing_imports` (posts)
  - 576 registros en `listing_import_media` (imaxes)
  
- **Almacenamento de imaxes**: Supabase Storage
  - Bucket: `instagram-import-media` (privado)
  - Todas as imaxes con URLs asinadas temporais (1 hora)
  
- **Status de revisión**: Todos os posts están en estado `pending_review` (á espera de revisión manual)

## Como Usar o Script

### Instalación

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### Importación de Batch (Múltiples Contas)

```powershell
# Importar con contas por defecto (5 contas, 10 posts cada una)
.\.venv\Scripts\python.exe import_instagram_batch.py

# Importar con 2 posts por conta (para probar)
.\.venv\Scripts\python.exe import_instagram_batch.py --limit 2

# Modo dry-run (previsualización sen gardar)
.\.venv\Scripts\python.exe import_instagram_batch.py --dry-run

# Importar contas específicas
.\.venv\Scripts\python.exe import_instagram_batch.py --usernames casa_japan old_houses asia

# Importar dende arquivo
.\.venv\Scripts\python.exe import_instagram_batch.py --account-list instagram_accounts.txt

# Gardar resultados a JSON
.\.venv\Scripts\python.exe import_instagram_batch.py --output resultados.json

# Todos os parámetros
.\.venv\Scripts\python.exe import_instagram_batch.py --account-list instagram_accounts.txt --limit 10 --output results.json --user-id admin
```

### Verificación de Datos

```powershell
# Ver estatísticas de importación
.\.venv\Scripts\python.exe verify_imports.py

# Ver posts pendentes de revisión
.\.venv\Scripts\python.exe -c "
from app.service import InstagramImportService
from app.config import get_settings

service = InstagramImportService(database_url=get_settings().effective_database_url)
drafts = service.list_pending_imports(user_id='batch-import-service')
print(f'Posts pendentes de revisión: {len(drafts)}')
for draft in drafts[:3]:
    print(f'  - {draft.account_username}: {len(draft.images)} imaxes')
"
```

## Estrutura de Ficheiros

```
backend/
├── import_instagram_batch.py    # Script principal para importación en batch
├── verify_imports.py             # Script de verificación de dados
├── instagram_accounts.txt        # Lista de contas (un nome por liña)
├── import_results.json           # Resultados da última importación
├── app/
│   ├── main.py                   # API FastAPI
│   ├── service.py                # Lóxica de negocio (Instagram + Listings)
│   ├── models.py                 # Modelos SQLAlchemy
│   ├── schemas.py                # Esquemas Pydantic
│   ├── media_storage.py          # Xestor de almacenamento Supabase
│   ├── config.py                 # Configuración de variables de contorno
│   ├── auth.py                   # Autenticación con JWT
│   └── database.py               # Factory de sesiones SQLAlchemy
└── tests/
    └── test_api.py               # Testes unitarios
```

## Endpoints da API

```
POST /api/v1/imports/instagram
  Importa posts de contas de Instagram
  
  Body:
  {
    "usernames": ["casa_japan"],    # Opcional: buscar nestes usernames
    "post_ids": [],                  # Opcional: IDs específicos de posts
    "limit": 10,                     # Posts a importar (1-50)
    "dry_run": true                  # Previsualización sen gardar
  }
  
  Resposta:
  {
    "account_id": "123456789",
    "dry_run": false,
    "drafts": [
      {
        "import_id": "uuid",
        "account_id": "123456789",
        "account_username": "casa_japan",
        "source_post_id": "123456789",
        "status": "pending_review",
        "title": "Casa tradicional en Kyoto",
        "caption": "Descripción completa...",
        "images": [
          {
            "position": 0,
            "media_type": "image",
            "url": "https://signed-url.example.com/image.jpg"
          }
        ]
      }
    ],
    "message": "Publicacións gardadas como borradores para revisión manual."
  }

GET /api/v1/imports/instagram?account_id=optional
  Lista os posts importados pendentes de revisión
  
  Resposta:
  [
    {
      "import_id": "uuid",
      "status": "pending_review",
      "images": [...],
      ...
    }
  ]
```

## Configuración de Contorno (.env)

```env
# Instagram
INSTAGRAM_GRAPH_ACCESS_TOKEN=your_token_here
INSTAGRAM_GRAPH_API_VERSION=v27.0

# Supabase Database
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_PROJECT_REF=your_project_ref
SUPABASE_DB_HOST=aws-1-eu-west-1.pooler.supabase.com
SUPABASE_DB_PORT=5432
SUPABASE_DB_PASSWORD=your_password

# Supabase Authentication
SUPABASE_JWT_SECRET=your_jwt_secret

# Supabase Storage
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key
SUPABASE_STORAGE_BUCKET=instagram-import-media

# Aplicación
APP_ENV=development
CORS_ORIGINS=http://localhost:3000
DATABASE_URL=sqlite:///./data/ensonho.db  # Ignorado se SUPABASE_DB_PASSWORD está configurado
```

## Próximos Pasos

1. **Revisión Manual**: Os posts importados están en estado `pending_review`. Precisas crear un endpoint para:
   - Revisar os posts e imaxes
   - Crear un anuncio (listing) a partir dun borrador
   - Rechazar ou editar os posts

2. **Mapeamento de Imaxes**: Conectar as imaxes importadas (`listing_import_media`) aos anuncios finais (`listing_media`)

3. **Metadatos**: Extraer información como:
   - Prezo (se está no título/caption)
   - Localización (prefectura/cidade)
   - Tipo de casa
   - Número de habitacións

4. **Busca e Filtros**: Engadir busca por localización, prezo, tipo de casa

5. **Calendario y Reservas**: Implementar sistema de dispoñibilidade

## Seguridade - ⚠️ IMPORTANTE

**As credenciais NO DEBEN gardarse no repositorio git:**
- Token de Instagram Graph API
- Chaves JWT de Supabase
- Chaves de servizo de Supabase
- Contraseña de base de datos

Estas están gardadas en `.env` que está en `.gitignore`.

Para producción:
- Usar AWS Secrets Manager, HashiCorp Vault, ou similar
- Configurar as variables de contorno no servidor
- Habilitar rotación de credenciais regularmente

## Troubleshooting

### Erro: "INSTAGRAM_GRAPH_ACCESS_TOKEN non está configurado"
Asegúrate de que a variable de contorno está configurada en `.env`

### Erro: "A persistencia das importacións non está configurada"
Asegúrate de que `SUPABASE_DB_PASSWORD` está configurado e a conexión a PostgreSQL é válida

### Erro: "SUPABASE_SERVICE_ROLE_KEY non está configurado"
Necesitas configurar a chave de servizo de Supabase para gardar imaxes en Storage

### Erro: Unicode en terminal Windows
O script usa caracteres ASCII para evitar problemas. Se aínda hai problemas:
```powershell
$env:PYTHONIOENCODING = "utf-8"
.\.venv\Scripts\python.exe import_instagram_batch.py
```

## Licencia

Parte do proxecto Ensonho - Portal inmobiliario de vivendas xaponesas
