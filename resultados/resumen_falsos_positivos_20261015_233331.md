| Corrida | Editor | Ediciones | Alertas | Esperadas | Espurias | Tasa de falsos positivos | Ediciones con problemas del editor |
|---|---|---:|---:|---:|---:|---:|---:|
| A_con_filtro | vim | 20 | 20 | 20 | 0 | 0.0 % | 0 |
| A_con_filtro | nano | 20 | 20 | 20 | 0 | 0.0 % | 0 |
| B_sin_filtro | vim | 20 | 40 | 20 | 20 | 50.0 % | 0 |
| B_sin_filtro | nano | 20 | 60 | 20 | 40 | 66.7 % | 0 |

Tasa de falsos positivos = alertas espurias / alertas totales.

Tipos de alertas espurias por corrida y editor:

- B_sin_filtro, vim: CREADO .vim.conf.swp (20)
- B_sin_filtro, nano: CREADO .nano.conf.swp (40)

Editores: VIM - Vi IMproved 9.1 (2024 Jan 02, compiled Aug 24 2026 22:13:04);  GNU nano, version 7.2. Sin configuración personal: rige la del sistema (Ubuntu: /etc/nanorc trae 'set locking', que crea los .swp de nano; vim usa backupcopy=yes, que guarda sobre el mismo archivo). Monitor en modo aprobación. Fecha: 15/10/2026 23:33.
