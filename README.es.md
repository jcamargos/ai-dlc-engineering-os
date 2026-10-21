<div align="center">

# AI-DLC Engineering OS

<img src="docs/assets/ai-dlc-social-preview.jpg" alt="AI-DLC Engineering OS" width="860" />

**[English](README.md) | [Português (Brasil)](README.pt-BR.md) | [Español](README.es.md)**

### Tus agentes olvidan el contexto entre sesiones. Conserva lo que importa.

**Memoria local para decisiones, incidentes y convenciones. Tú apruebas qué se convierte en regla.**

[![CI](https://github.com/jcamargos/ai-dlc-engineering-os/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/jcamargos/ai-dlc-engineering-os/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/ai-dlc-engineering-os)](https://pypi.org/project/ai-dlc-engineering-os/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)

**[Inicio rápido](#inicio-rápido) · [Evidencias](#evidencias) · [Cómo funciona](#cómo-funciona) · [Preguntas frecuentes](#preguntas-frecuentes)**

<img src="docs/assets/cross-session-demo.svg" alt="Una sesión guarda una decisión; otra la recupera. Se rechaza una credencial." width="860" />

**Para Claude Code, Codex y VS Code mediante MCP. Gratuito y de código abierto (Apache 2.0).**

</div>

El lunes tu agente aprende que los pagos necesitan claves de idempotencia. El martes,
en otra sesión o editor, vuelve a empezar. AI-DLC comparte memoria persistente del
proyecto entre clientes MCP configurados en la misma máquina y ofrece 26 contratos
de especialistas. Las reglas requieren evidencia y aprobación humana.

El servidor usa SQLite local: sin cuenta, telemetría ni servicio alojado obligatorio.
Tu cliente de IA decide qué contexto recuperado envía a su proveedor de modelos.

## Inicio rápido

Instala [uv](https://docs.astral.sh/uv/getting-started/installation/) y ejecuta en Windows, macOS o Linux:

```bash
uvx ai-dlc-engineering-os setup
```

Selecciona Codex, Claude Code o VS Code, revisa los cambios y confirma. El asistente
instala un entorno persistente, respalda la configuración y la memoria existentes,
registra MCP y verifica los editores seleccionados. Reinicia el editor después.
VS Code debe haberse abierto al menos una vez para crear su perfil predeterminado.

Abre tu proyecto y pregunta:

```text
¿Qué sabemos de este código antes de modificar el flujo de pagos?
```

En Claude Code y Codex, la instalación añade instrucciones a `CLAUDE.md` y `AGENTS.md`
para consultar decisiones, lecciones e incidentes antes de cambios importantes.
Pide explícitamente guardar una decisión duradera para recuperarla en otra sesión.

Usa `--editors codex,claude --dry-run` para revisar sin aplicar cambios; para una
instalación desatendida especifica `--editors` y añade `--yes`.
La [guía de instalación](docs/INSTALLATION.md) cubre requisitos, actualizaciones,
versiones fijadas, copias de seguridad y desinstalación.

## ¿Por qué no usar solo CLAUDE.md o AGENTS.md?

Conserva esos archivos para las instrucciones escritas por ti. La memoria añade:

| Necesidad | Archivo de instrucciones | AI-DLC Engineering OS |
|---|---|---|
| Autoría | Tú escribes | Los agentes proponen; tú apruebas reglas |
| Varios editores | Configuración por herramienta | Una base local compartida |
| Contexto creciente | Se carga el archivo | Se recupera contexto relevante |
| Información obsoleta | Edición manual | Sustitución con historial; código y pruebas prevalecen |
| Credenciales accidentales | Pueden quedar guardadas | Se rechazan al escribir |

## Evidencias

Las cifras históricas siguientes proceden de una máquina Linux de 2 vCPU con Python
3.13. Son referencias, no garantías de capacidad. Consulta el [protocolo](benchmarks/README.md)
y ejecuta las pruebas de tu checkout para obtener resultados actuales.

| Comprobación | Resultado de referencia | Reproducir |
|---|---|---|
| Memoria entre procesos | Decisión recuperada; credencial rechazada | `python scripts/demo_cross_session.py` |
| Swarm: 500 tareas, 8 trabajadores | 500 completadas, 0 duplicadas y 0 perdidas | `python benchmarks/run_reliability.py --tasks 500 --workers 8` |
| Recuperación: 1.000 memorias | 200/200 búsquedas con resultados; media de 104 ms | `ai-dlc benchmark --operations 1000 --searches 200` |
| Suite actual | Incluye transporte MCP real, migraciones y grafo | `pytest` |

## Funciones

| Capacidad | Comportamiento |
|---|---|
| Memoria persistente | FTS5/BM25 y búsqueda vectorial local sobre decisiones, lecciones, incidentes y resultados |
| Protección de contexto | Rechazo de credenciales; contenido similar a instrucciones marcado y retenido |
| Gobierno humano | Solo una persona aprueba reglas con `ai-dlc-admin` en una terminal interactiva |
| 26 especialistas | Contratos, procedimientos, listas de comprobación y criterios de escalado |
| Evolución verificable | Casos de evaluación, controles de calidad y seguridad, despliegue gradual y detección de deriva |

## Cómo funciona

<img src="docs/assets/engineering-workflow.svg" alt="Cargar contexto, seleccionar especialistas, verificar y conservar conocimiento duradero" width="1100" />

1. `resolve_project_id` y `get_project_context`: decisiones, lecciones e incidentes relevantes.
2. `list_agents` y `get_agent_context`: contrato y reglas del especialista apropiado.
3. Realiza el trabajo y guarda hechos duraderos con `save_decision`, `record_learning` o `record_incident`.
4. `record_task_outcome`: registra el resultado con evidencia. Las lecciones empiezan como candidatas; las reglas requieren aprobación humana.

La base SQLite está en `~/.ai-dlc/memory/memory.db`, con WAL. Instalaciones anteriores
a 3.2.0 siguen usando `~/.codex/ai-dlc-memory` automáticamente. Las migraciones tienen
versión y la instalación conserva una copia de seguridad.
Consulta [arquitectura](docs/ARCHITECTURE.md), [aprendizaje](docs/LEARNING_MODEL.md)
y [evolución de agentes](docs/AGENT_EVOLUTION.md).

## Grafo de importaciones del repositorio (opcional)

Disponible en este checkout; instala esta revisión para usar el grafo. La versión de PyPI puede ir detrás de main.

Antes de editar un módulo, consulta sus dependencias o dependientes transitivos.
El grafo local devuelve rutas, líneas de origen, profundidad limitada y cobertura.
Python usa AST; JavaScript/TypeScript usa una aproximación léxica.
Cada consulta verifica la vigencia y rechaza resultados obsoletos hasta actualizar el índice.

Configura `AI_DLC_GRAPH_ROOTS` con las raíces Git locales autorizadas y usa
`index_repository_graph`, `repository_graph_status` y `query_repository_graph`.
El acceso está desactivado por defecto; no almacena cuerpos de código ni necesita
un servicio externo. Es un grafo de importaciones, no un grafo completo de llamadas
ni una promesa medida de ahorro de tokens.
Consulta [configuración, límites y reversión](docs/REPOSITORY_GRAPH.md).

```shell
python scripts/demo_repository_graph.py
```

## Los 26 agentes

| Área | Agentes |
|---|---|
| Coordinación | `orchestrator`, `planner-requirements`, `product`, `research`, `knowledge-curator` |
| Arquitectura y construcción | `principal-architect`, `backend`, `frontend`, `data-database`, `integration-api`, `migration`, `ai-llm`, `ux-product-design`, `developer-experience` |
| Calidad | `code-review`, `qa-verification`, `performance` |
| Seguridad | `security`, `threat-model`, `red-team`, `governance-compliance` |
| Operaciones | `platform-sre`, `observability`, `incident-response`, `release`, `cloud-finops` |

Contratos en [contracts/agent_contracts.json](contracts/agent_contracts.json) y
guías en [src/ai_dlc_mcp/agents](src/ai_dlc_mcp/agents/). Claude Code también dispone
de subagentes `ai-dlc-*`. Consulta [agentes nativos](docs/NATIVE_AGENTS.md) para
Codex, VS Code/Copilot y Cursor y sus límites de verificación en el editor.
Estas definiciones heredan el modelo y los permisos del cliente.

## Comandos

| Comando | Finalidad |
|---|---|
| `ai-dlc-admin` | Revisar candidatos y reglas, verificar lecciones, administrar releases, exportar, respaldar y auditar |
| `ai-dlc-install install \| uninstall \| doctor` | Registrar, retirar o comprobar MCP |
| `ai-dlc init` | Configuración del proyecto; `--project-mcp` también escribe `.mcp.json` |
| `ai-dlc doctor` | Comprobar la instalación local |

<details>
<summary><strong>Avanzado: swarms, Mission Control, hooks y SDKs</strong></summary>

- **Swarms** (`ai-dlc swarm …`): grafos persistentes de tareas con dependencias, leases atómicos y worktrees aislados.
- **Mission Control** (`ai-dlc mission-control`): panel local, limitado a loopback por defecto.
- **Hooks**: eventos de sesión, prompt, herramienta y parada; los fallos no bloquean el cliente.
- **SDKs Python y TypeScript**: conectan por MCP Streamable HTTP solo al servidor configurado con `AI_DLC_REMOTE_URL`.
- **Federación**: desactivada salvo que se configure `AI_DLC_ENABLE_FEDERATION=1`.

Consulta [capacidades avanzadas](docs/ADVANCED.md), incluidos los identificadores
heredados que se mantienen por compatibilidad.

</details>

## Modelo de seguridad

- Las escrituras rechazan claves, tokens, claves privadas y cadenas de conexión detectadas.
- El contenido que parece una inyección de instrucciones se marca y se excluye del contexto.
- Las aprobaciones humanas y operaciones administrativas sensibles exigen terminal interactiva y confirmación escrita.
- No hay acceso de red por defecto. Mission Control escucha en loopback y rechaza hosts externos.
- El grafo solo lee raíces autorizadas, limita archivos y bytes y no ejecuta el código indexado.

Informa de vulnerabilidades en privado según [SECURITY.md](SECURITY.md).

## Preguntas frecuentes

<details>
<summary><strong>¿Salen de mi máquina el código o la memoria?</strong></summary>

El servidor guarda la memoria localmente y no tiene telemetría. Tu cliente de IA
puede enviar contexto recuperado a su proveedor según su configuración. Federación
y SDKs remotos son opcionales.

</details>

<details>
<summary><strong>¿Los editores comparten memoria?</strong></summary>

Sí, cuando usan el mismo directorio de datos. Una decisión guardada desde un cliente
está disponible para los demás.

</details>

<details>
<summary><strong>¿Qué pasa con una instalación antigua?</strong></summary>

La memoria permanece en `~/.codex/ai-dlc-memory` y se sigue utilizando. No se mueve
automáticamente. Para adoptar la nueva ruta, cierra los editores y mueve esa carpeta
a `~/.ai-dlc/memory`.

</details>

<details>
<summary><strong>¿Se sobrescribe mi configuración?</strong></summary>

El instalador modifica sus bloques o entradas administradas y conserva copias
con fecha. No sustituye el resto de tus instrucciones.

</details>

<details>
<summary><strong>¿Puede un agente aprobar sus propias reglas?</strong></summary>

No. Puede proponerlas; aprobarlas requiere `ai-dlc-admin` en una terminal interactiva.
Los contratos orientan al agente, no entrenan ni sustituyen su modelo.

</details>

## Documentación

| Guía | Contenido |
|---|---|
| [Instalación](docs/INSTALLATION.md) | Instalación, actualización, copias y desinstalación |
| [Arquitectura](docs/ARCHITECTURE.md) | MCP, SQLite y límites de confianza |
| [Aprendizaje](docs/LEARNING_MODEL.md) | Evidencia y ciclo de conocimiento |
| [Evolución](docs/AGENT_EVOLUTION.md) | Evaluaciones, releases y deriva |
| [Capacidades avanzadas](docs/ADVANCED.md) | Swarms, panel, hooks y funciones opcionales |
| [Grafo](docs/REPOSITORY_GRAPH.md) | Importaciones, actualización, límites y seguridad |
| [Benchmarks](benchmarks/README.md) | Mediciones reproducibles |
| [Seguridad](SECURITY.md) | Política de notificación |
| [Changelog](CHANGELOG.md) | Historial de versiones |

## Desinstalación

Ejecuta `ai-dlc-install uninstall --no-cli` antes de
`uv tool uninstall ai-dlc-engineering-os`. Se conserva la memoria.
Consulta [detalles de desinstalación](docs/INSTALLATION.md#uninstall).

## Contribuir

Se aceptan issues y pull requests. Lee [CONTRIBUTING.md](CONTRIBUTING.md), incluido
el DCO (`git commit -s`). Mantén sincronizados los tres READMEs.
Sin afiliación con Anthropic, OpenAI, Microsoft o GitHub.

Creado por José Camargo · [LinkedIn](https://www.linkedin.com/in/joseacamargo) · [Instagram](https://www.instagram.com/jcamarguinho)
