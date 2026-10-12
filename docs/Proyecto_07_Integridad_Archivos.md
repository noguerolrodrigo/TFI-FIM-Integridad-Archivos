# Proyecto 7: Monitoreo Automatizado de Integridad de Archivos (FIM)

## 📋 Información General

**Nivel de Dificultad**: Básico-Intermedio
**Tiempo Estimado**: 6-8 horas
**Categoría**: System Hardening & Intrusion Detection

## 🎯 Objetivos de Aprendizaje

1. Comprender la importancia del File Integrity Monitoring (FIM)
2. Implementar sistemas de detección de cambios no autorizados
3. Utilizar algoritmos de hashing para verificación de integridad
4. Automatizar alertas ante modificaciones sospechosas
5. Implementar respuestas automatizadas ante compromisos

## 🔧 Herramientas

- **N8N**: Automatización
- **AIDE** o **Tripwire**: FIM tradicional (opcional)
- **Python hashlib**: Generación de hashes
- **inotify-tools**: Monitoreo en tiempo real (Linux)
- **PostgreSQL**: Base de datos de hashes

## 🏗️ Arquitectura

```
┌────────────────────────────────────────────┐
│     Sistema de Integridad de Archivos     │
│                                            │
│  ┌──────────────┐      ┌──────────────┐   │
│  │  Directories │─────▶│     N8N      │   │
│  │ to Monitor   │      │  (Scanner)   │   │
│  └──────────────┘      └──────┬───────┘   │
│                               │           │
│                        ┌──────▼───────┐   │
│                        │  PostgreSQL  │   │
│                        │  (Hashes DB) │   │
│                        └──────┬───────┘   │
│                               │           │
│                        ┌──────▼───────┐   │
│                        │    Alerts    │   │
│                        └──────────────┘   │
└────────────────────────────────────────────┘
```

## 💻 Implementación

### Base de Datos

```sql
CREATE DATABASE file_integrity;

\c file_integrity

CREATE TABLE file_hashes (
    id SERIAL PRIMARY KEY,
    file_path TEXT NOT NULL,
    file_name VARCHAR(500),
    hash_md5 VARCHAR(32),
    hash_sha256 VARCHAR(64),
    file_size BIGINT,
    permissions VARCHAR(10),
    owner VARCHAR(100),
    last_modified TIMESTAMP,
    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_checked TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_modified BOOLEAN DEFAULT false
);

CREATE TABLE file_changes (
    id SERIAL PRIMARY KEY,
    file_id INTEGER REFERENCES file_hashes(id),
    change_type VARCHAR(50), -- modified, deleted, created, permissions_changed
    old_hash VARCHAR(64),
    new_hash VARCHAR(64),
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    severity VARCHAR(20) DEFAULT 'medium'
);

CREATE INDEX idx_file_path ON file_hashes(file_path);
CREATE INDEX idx_last_checked ON file_hashes(last_checked);
CREATE INDEX idx_changes_detected ON file_changes(detected_at);
```

### Script Python de Monitoreo

```python
#!/usr/bin/env python3
import hashlib
import os
import psycopg2
from pathlib import Path
from datetime import datetime

DB_CONFIG = {
    'host': 'localhost',
    'database': 'file_integrity',
    'user': 'db_user',
    'password': 'db_pass'
}

MONITORED_DIRS = [
    '/etc',
    '/bin',
    '/sbin',
    '/usr/bin',
    '/usr/sbin',
    '/var/www'
]

EXCLUDED_PATTERNS = [
    '*.log',
    '*.tmp',
    '/proc/*',
    '/sys/*'
]

def calculate_hashes(file_path):
    """Calcula MD5 y SHA256 de un archivo"""
    md5_hash = hashlib.md5()
    sha256_hash = hashlib.sha256()

    try:
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                md5_hash.update(chunk)
                sha256_hash.update(chunk)

        return md5_hash.hexdigest(), sha256_hash.hexdigest()
    except (PermissionError, FileNotFoundError) as e:
        return None, None

def get_file_metadata(file_path):
    """Obtiene metadatos del archivo"""
    try:
        stat = os.stat(file_path)
        return {
            'size': stat.st_size,
            'permissions': oct(stat.st_mode)[-3:],
            'owner': Path(file_path).owner(),
            'modified': datetime.fromtimestamp(stat.st_mtime)
        }
    except Exception:
        return None

def scan_directory(directory, conn):
    """Escanea directorio y verifica integridad"""
    cursor = conn.cursor()
    changes_detected = []

    for root, dirs, files in os.walk(directory):
        # Excluir directorios del sistema
        dirs[:] = [d for d in dirs if not any(d.startswith(ex) for ex in ['.', 'proc', 'sys'])]

        for file_name in files:
            file_path = os.path.join(root, file_name)

            # Calcular hashes
            md5, sha256 = calculate_hashes(file_path)
            if not md5:
                continue

            # Obtener metadatos
            metadata = get_file_metadata(file_path)
            if not metadata:
                continue

            # Verificar en base de datos
            cursor.execute("""
                SELECT id, hash_sha256, file_size, permissions
                FROM file_hashes
                WHERE file_path = %s
            """, (file_path,))

            existing = cursor.fetchone()

            if existing:
                # Archivo existe, verificar cambios
                file_id, old_hash, old_size, old_perms = existing

                if sha256 != old_hash:
                    # Contenido modificado
                    cursor.execute("""
                        INSERT INTO file_changes (file_id, change_type, old_hash, new_hash, severity)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (file_id, 'modified', old_hash, sha256, 'high'))

                    changes_detected.append({
                        'type': 'modified',
                        'path': file_path,
                        'old_hash': old_hash,
                        'new_hash': sha256
                    })

                elif metadata['permissions'] != old_perms:
                    # Permisos cambiados
                    cursor.execute("""
                        INSERT INTO file_changes (file_id, change_type, severity)
                        VALUES (%s, %s, %s)
                    """, (file_id, 'permissions_changed', 'medium'))

                    changes_detected.append({
                        'type': 'permissions',
                        'path': file_path
                    })

                # Actualizar registro
                cursor.execute("""
                    UPDATE file_hashes
                    SET hash_md5 = %s, hash_sha256 = %s, file_size = %s,
                        permissions = %s, last_modified = %s, last_checked = NOW(),
                        is_modified = %s
                    WHERE id = %s
                """, (md5, sha256, metadata['size'], metadata['permissions'],
                      metadata['modified'], sha256 != old_hash, file_id))

            else:
                # Archivo nuevo
                cursor.execute("""
                    INSERT INTO file_hashes (
                        file_path, file_name, hash_md5, hash_sha256,
                        file_size, permissions, owner, last_modified
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (file_path, file_name, md5, sha256, metadata['size'],
                      metadata['permissions'], metadata['owner'], metadata['modified']))

                file_id = cursor.fetchone()[0]

                cursor.execute("""
                    INSERT INTO file_changes (file_id, change_type, new_hash, severity)
                    VALUES (%s, %s, %s, %s)
                """, (file_id, 'created', sha256, 'low'))

                changes_detected.append({
                    'type': 'created',
                    'path': file_path
                })

    conn.commit()
    cursor.close()

    return changes_detected

def main():
    conn = psycopg2.connect(**DB_CONFIG)

    print(f"[{datetime.now()}] Iniciando escaneo de integridad...")

    all_changes = []
    for directory in MONITORED_DIRS:
        if os.path.exists(directory):
            print(f"Escaneando: {directory}")
            changes = scan_directory(directory, conn)
            all_changes.extend(changes)

    conn.close()

    print(f"\nEscaneo completado: {len(all_changes)} cambios detectados")

    if all_changes:
        print("\nCambios detectados:")
        for change in all_changes[:10]:  # Mostrar primeros 10
            print(f"  - [{change['type']}] {change['path']}")

if __name__ == '__main__':
    main()
```

### Workflow N8N

```javascript
// Nodo N8N: Ejecutar escaneo periódico

// Ejecutar script Python
const { exec } = require('child_process');
const { promisify } = require('util');
const execAsync = promisify(exec);

const { stdout, stderr } = await execAsync('python3 /path/to/fim_scanner.py');

// Verificar cambios críticos en base de datos
const { Client } = require('pg');
const client = new Client({
  host: 'localhost',
  database: 'file_integrity',
  user: 'db_user',
  password: 'db_pass'
});

await client.connect();

const recentChanges = await client.query(`
  SELECT
    fc.change_type,
    fc.severity,
    fh.file_path,
    fh.file_name,
    fc.detected_at
  FROM file_changes fc
  JOIN file_hashes fh ON fh.id = fc.file_id
  WHERE fc.detected_at >= NOW() - INTERVAL '5 minutes'
    AND fc.severity IN ('high', 'critical')
  ORDER BY fc.detected_at DESC
`);

await client.end();

// Generar alerta si hay cambios críticos
if (recentChanges.rows.length > 0) {
  return [{
    json: {
      alertType: 'file_integrity_violation',
      changesDetected: recentChanges.rows.length,
      changes: recentChanges.rows,
      requiresAction: true
    }
  }];
} else {
  return [{
    json: {
      status: 'ok',
      message: 'No se detectaron cambios críticos',
      requiresAction: false
    }
  }];
}
```

## 📝 Ejercicios

### Ejercicio 1: Setup (2 horas)
- Configurar base de datos
- Ejecutar primer escaneo baseline
- Documentar archivos monitoreados

### Ejercicio 2: Simulación (2 horas)
- Modificar archivos intencionalmente
- Verificar detección de cambios
- Analizar alertas generadas

### Ejercicio 3: Respuesta Automatizada (4 horas)
- Implementar restauración automática
- Crear sistema de cuarentena
- Configurar notificaciones

## 🏆 Evaluación

| Criterio | Puntos |
|----------|--------|
| Implementación correcta | 30 |
| Cobertura de monitoreo | 25 |
| Sistema de alertas | 25 |
| Documentación | 20 |

---

**Autor**: Materia de Seguridad Ofensiva
