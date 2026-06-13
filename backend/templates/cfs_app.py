"""最小の cFS アプリ「穴あきテンプレ」（sample_app 風）。

決定論側（このモジュールが生成）:
  app名・コマンドコード・テレメトリ構造体・init/runloop/SBパイプ/ディスパッチ/HK送出。
非決定論側（穴 = LLMが埋める）:
  業務ロジック（HKテレメトリの値詰め・各コマンドハンドラ本体）。

「LLMが触るのは穴埋めだけ。配線・MID・構造は決定論で固定」という分離を体現する。
"""
from __future__ import annotations

import re
from string import Template

from ..models import GeneratedFile, StructuredRequirement


def _aid(name: str) -> str:
    """app名をC識別子向けに正規化（小文字）。"""
    s = re.sub(r"[^A-Za-z0-9_]", "_", name or "").strip("_")
    return (s or "sample_app").lower()


def _cid(name: str) -> str:
    """コマンド/フィールド名をC識別子向けに正規化。"""
    s = re.sub(r"[^A-Za-z0-9_]", "_", name or "").strip("_")
    return s or "FIELD"


def hole_specs(req: StructuredRequirement) -> dict[str, str]:
    """埋めるべき穴の一覧（hole_id -> 説明）。"""
    holes: dict[str, str] = {
        "hk_logic": "HKテレメトリ構造体（Payload）の各フィールドを最新値で埋める処理。",
    }
    for c in req.commands:
        cc = _cid(c.name).upper()
        holes[f"cmd_{cc}"] = c.summary or f"{c.name} コマンドの処理。"
    return holes


def render(req: StructuredRequirement, holes: dict[str, str]) -> list[GeneratedFile]:
    app = _aid(req.app_name)
    APP = app.upper()
    return [
        GeneratedFile(path=f"{app}/fsw/src/{app}_app.h", content=_header(req, app, APP)),
        GeneratedFile(path=f"{app}/fsw/src/{app}_app.c", content=_source(req, app, APP, holes)),
        GeneratedFile(path=f"{app}/CMakeLists.txt", content=_cmake(app, APP)),
    ]


def _indent(code: str, n: int = 4) -> str:
    pad = " " * n
    return "\n".join((pad + line) if line.strip() else line for line in (code or "").splitlines())


def _header(req: StructuredRequirement, app: str, APP: str) -> str:
    cmd_defines = "\n".join(
        f"#define {APP}_{_cid(c.name).upper()}_CC   {i}" for i, c in enumerate(req.commands)
    ) or f"#define {APP}_NOOP_CC   0"

    fields: list[str] = []
    seen: set[str] = set()
    for t in req.telemetry:
        for f in t.fields:
            fid = _cid(f)
            if fid not in seen:
                seen.add(fid)
                fields.append(f"    uint32 {fid};")
    tlm_fields = "\n".join(fields) or "    uint32 Reserved;"

    return Template(
        """#ifndef ${APP}_APP_H
#define ${APP}_APP_H

#include "cfe.h"

/* --- Command Codes (deterministic) --- */
${cmd_defines}

/* --- Housekeeping Telemetry Payload --- */
typedef struct
{
    uint8  CommandCounter;
    uint8  CommandErrorCounter;
${tlm_fields}
} ${APP}_HkTlm_Payload_t;

typedef struct
{
    CFE_MSG_TelemetryHeader_t TelemetryHeader;
    ${APP}_HkTlm_Payload_t    Payload;
} ${APP}_HkTlm_t;

/* --- Application Data --- */
typedef struct
{
    CFE_SB_PipeId_t CommandPipe;
    ${APP}_HkTlm_t  HkTlm;
} ${APP}_AppData_t;

void ${APP}_AppMain(void);

#endif /* ${APP}_APP_H */
"""
    ).safe_substitute(APP=APP, cmd_defines=cmd_defines, tlm_fields=tlm_fields)


def _source(req: StructuredRequirement, app: str, APP: str, holes: dict[str, str]) -> str:
    cmds = [_cid(c.name).upper() for c in req.commands] or ["NOOP"]

    cmd_decls = "\n".join(
        f"static void {APP}_{cc}(const CFE_SB_Buffer_t *SBBufPtr);" for cc in cmds
    )
    cmd_dispatch = "\n".join(
        f"        case {APP}_{cc}_CC:\n            {APP}_{cc}(SBBufPtr);\n            break;" for cc in cmds
    )
    cmd_funcs = "\n\n".join(
        Template(
            """static void ${APP}_${cc}(const CFE_SB_Buffer_t *SBBufPtr)
{
${body}
}"""
        ).safe_substitute(APP=APP, cc=cc, body=_indent(holes.get(f"cmd_{cc}", f"/* TODO(@LLM): {cc} */")))
        for cc in cmds
    )

    hk_logic = _indent(holes.get("hk_logic", "/* TODO(@LLM): populate telemetry fields */"))

    return Template(
        """#include "${app}_app.h"
#include <string.h>

${APP}_AppData_t ${APP}_AppData;

static int32 ${APP}_Init(void);
static void  ${APP}_ProcessCommandPacket(const CFE_SB_Buffer_t *SBBufPtr);
static void  ${APP}_SendHousekeeping(void);
${cmd_decls}

void ${APP}_AppMain(void)
{
    int32            status;
    CFE_SB_Buffer_t *SBBufPtr;

    status = ${APP}_Init();
    if (status != CFE_SUCCESS)
    {
        CFE_ES_WriteToSysLog("${APP}: init failed (0x%08lX)\\n", (unsigned long)status);
    }

    while (CFE_ES_RunLoop(NULL) == true)
    {
        status = CFE_SB_ReceiveBuffer(&SBBufPtr, ${APP}_AppData.CommandPipe, CFE_SB_PEND_FOREVER);
        if (status == CFE_SUCCESS)
        {
            ${APP}_ProcessCommandPacket(SBBufPtr);
        }
    }

    CFE_ES_ExitApp(CFE_ES_RunStatus_APP_EXIT);
}

static int32 ${APP}_Init(void)
{
    memset(&${APP}_AppData, 0, sizeof(${APP}_AppData));

    /* Deterministic wiring: create command pipe + subscribe to MIDs */
    return CFE_SB_CreatePipe(&${APP}_AppData.CommandPipe, 16, "${APP}_CMD_PIPE");
}

static void ${APP}_ProcessCommandPacket(const CFE_SB_Buffer_t *SBBufPtr)
{
    CFE_MSG_FcnCode_t cc = 0;
    CFE_MSG_GetFcnCode(&SBBufPtr->Msg, &cc);

    switch (cc)
    {
${cmd_dispatch}
        default:
            ${APP}_AppData.HkTlm.Payload.CommandErrorCounter++;
            break;
    }
}

static void ${APP}_SendHousekeeping(void)
{
    /* @LLM hole: hk_logic */
${hk_logic}
    CFE_SB_TimeStampMsg(CFE_MSG_PTR(${APP}_AppData.HkTlm.TelemetryHeader));
    CFE_SB_TransmitMsg(CFE_MSG_PTR(${APP}_AppData.HkTlm.TelemetryHeader), true);
}

${cmd_funcs}
"""
    ).safe_substitute(
        app=app,
        APP=APP,
        cmd_decls=cmd_decls,
        cmd_dispatch=cmd_dispatch,
        hk_logic=hk_logic,
        cmd_funcs=cmd_funcs,
    )


def _cmake(app: str, APP: str) -> str:
    return Template(
        """project(${APP}_APP C)

include_directories(fsw/src)
include_directories($${CFE_SOURCE_DIR}/modules/core_api/fsw/inc)

add_cfe_app(${app} fsw/src/${app}_app.c)
"""
    ).safe_substitute(app=app, APP=APP)
