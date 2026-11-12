# Quick Reference - Importación de Instagram

## Resumo Rápido
```
✅ 50 posts importados
✅ 576 imaxes descargadas
✅ PostgreSQL (Supabase) configurado
✅ Imaxes en Supabase Storage
✅ Scripts de xestión listos
```

## Comandos Principais

### Verificación
```bash
# Ver estatísticas
python show_import_stats.py

# Detalles completos
python verify_imports.py
```

### Importación Nueva (Se queres máis posts)
```bash
# Importar 10 posts por conta (por defecto)
python import_instagram_batch.py

# Importar 5 posts por conta (máis rápido)
python import_instagram_batch.py --limit 5

# Importar contas específicas
python import_instagram_batch.py --usernames casa_japan akiya_tours

# Previsualización sen gardar
python import_instagram_batch.py --dry-run

# Gardar resultados
python import_instagram_batch.py --output results.json
```

### Xestión de Posts
```bash
# Listar pendentes (NOTA: precisa user_id válido)
# Actualmente todos os posts están con user_id:
# a9a34161-7914-4c1e-8042-fc1da4d4a630

python manage_imports.py list --user-id a9a34161-7914-4c1e-8042-fc1da4d4a630

# Exportar post como JSON para edición manual
python manage_imports.py export {IMPORT_ID} --output post.json

# Aprobar post (crea un listing)
python manage_imports.py approve {IMPORT_ID} --title "Título" --prefecture "Kyoto"

# Rechazar post
python manage_imports.py reject {IMPORT_ID} --reason "Foto de baja calidade"
```

## URLs Útiles

- **Supabase Console**: https://app.supabase.com/project/tdxfwumdmanmfxzoytpm
- **Bucket Storage**: Ir a Storage > instagram-import-media
- **Database**: SQL Editor (ver táboas: listing_imports, listing_import_media)

## Estrutura de Datos

### Taboa: listing_imports (50 filas)
```sql
SELECT id, source_account_id, source_post_id, status, created_at 
FROM listing_imports 
LIMIT 5;
```

### Taboa: listing_import_media (576 filas)
```sql
SELECT import_id, position, media_type, storage_path 
FROM listing_import_media 
LIMIT 5;
```

## Información de Conexión

**Base de datos**: PostgreSQL (Supabase)
- Host: `aws-1-eu-west-1.pooler.supabase.com`
- Puerto: `5432`
- Base: `postgres`
- Usuario: `postgres.tdxfwumdmanmfxzoytpm`
- Contraseña: Guardada en `.env` (SUPABASE_DB_PASSWORD)

**Storage**: Supabase Storage
- Bucket: `instagram-import-media`
- Chave: Guardada en `.env` (SUPABASE_SERVICE_ROLE_KEY)

## Estado Actual

| Taboa | Filas | Status |
|-------|-------|--------|
| listing_imports | 50 | pending_review |
| listing_import_media | 576 | associated |
| Supabase Storage | 576 ficheiros | private, signed URLs |

## Próximos Pasos

1. **Revisar Manualmente**
   - Accede a https://app.supabase.com
   - Revisa os posts en listing_imports
   - Edita títulos, descripcións, precos

2. **Aprobar Posts**
   - Usa `manage_imports.py approve` para crear listings
   - Isto moverá o post a estado "approved"
   - Creará un registro en tabla "listings"

3. **Ver no Frontend**
   - Accede a http://localhost:3000
   - Os anuncios aprobados apareceran

## Troubleshooting

**Erro: "invalid input syntax for type uuid"**
→ Usar UUID válido dende base datos

**Erro: "UnicodeEncodeError"**
→ Caracteres unicode no terminal Windows. Os scripts xa están fixados.

**Imaxes non aparecen**
→ Chequear que Supabase Storage está configurado e bucket existe

**Posts non se garda en database**
→ Chequear que DATABASE_URL apunta a PostgreSQL, non SQLite

## Ficheiros Importantes

```
backend/
├── import_instagram_batch.py    ← Script principal
├── verify_imports.py            ← Ver datos
├── manage_imports.py            ← Xestionar posts
├── show_import_stats.py         ← Estadísticas
├── instagram_accounts.txt       ← Contas a importar
├── import_results.json          ← Resultados últimas
└── INSTAGRAM_IMPORT.md          ← Documentación completa
```

## Seguridade

**NON expor:**
- `.env` (contén credenciais)
- SUPABASE_SERVICE_ROLE_KEY
- INSTAGRAM_GRAPH_ACCESS_TOKEN
- SUPABASE_DB_PASSWORD

Todas as credenciais están en `.env` que xa está en `.gitignore`.

---

**Last Updated**: 2026-11-12  
**Status**: ✅ Completado e testeado
