Copia de /etc: 719 archivos legibles, 1.1 MB. Fecha: 15/10/2026 23:54.

**Duración medida de un escaneo completo (S)**, 20 veces: mediana 9.7 ms, p95 10.6 ms, mínimo 9.2 ms, máximo 11.5 ms.

**Validación con T = 10 s** (30 cambios en instantes al azar): detección media medida 4.45 s (mediana 4.29 s, máximo 9.10 s). La fórmula T/2 + S da 5.01 s.

**Cálculo teórico con el S medido** (no medido para estos T):

| Período T | Detección media ≈ T/2 + S | Detección máxima ≈ T + S |
|---|---:|---:|
| 10 s (medido arriba) | 5.0 s | 10.0 s |
| 1 min | 30.0 s | 60.0 s |
| 5 min | 150.0 s | 300.0 s |
| 1 h | 1800.0 s | 3600.0 s |

S se toma completo como cota superior: en un escaneo real el archivo cambiado puede aparecer antes del final del recorrido.
