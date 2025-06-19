# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = [('mcp_local/mcp_agent.config.yaml', 'mcp_local'), ('mcp_local/mcp_agent.secrets.yaml', 'mcp_local'), ('venv/lib/python3.11/site-packages/unstructured/nlp/english-words.txt', 'unstructured/nlp'), ('venv/lib/python3.11/site-packages/onnxruntime/tools/symbolic_shape_infer.py', 'onnxruntime/tools')]
binaries = []
hiddenimports = ['onnx', 'tensorboard', 'mx.DateTime', 'scipy.special._cdflib', 'importlib_resources.trees', 'uvicorn.logging', 'uvicorn.loops', 'uvicorn.loops.auto', 'uvicorn.protocols', 'uvicorn.protocols.http', 'uvicorn.protocols.http.auto', 'uvicorn.protocols.websockets', 'uvicorn.protocols.websockets.auto', 'uvicorn.lifespan', 'uvicorn.lifespan.on', 'fastapi_another_json_patch', 'mcp_server_fetch', 'mcp_local.servers.qdrant', 'mcp_local.servers.qdrant.main', 'mcp_local.servers.qdrant.server', 'mcp_local.servers.qdrant.mcp_server', 'mcp_local.servers.qdrant.qdrant', 'mcp_local.servers.qdrant.settings', 'mcp_local.servers.qdrant.embeddings', 'mcp_local.servers.qdrant.embeddings.base', 'mcp_local.servers.qdrant.embeddings.factory', 'mcp_local.servers.qdrant.embeddings.fastembed', 'mcp_local.servers.qdrant.embeddings.types', 'fastembed', 'fastembed.common', 'fastembed.common.model_description', 'mcp_local.servers.websearch.server', 'mcp_local.servers.document_loader.server', 'mcp_local.servers.markdown_editor.server', 'mcp_local.servers.markdown_editor.markdown_editor', 'mcp_local.servers.markdown_editor.markdown_converter', 'mcp_local.servers.markdown_editor.markdown_preview', 'mcp_local.servers.markdown_editor.markdown_integration', 'mcp_local.servers.markdown_editor.chart_generator', 'mcp_local.servers.markdown_editor.table_generator', 'mcp_local.core.shared_workspace', 'mcp_local.core.websocket_manager', 'aiohttp', 'aiohttp.client', 'aiohttp.connector', 'services.background_preloader', 'services.mcp_server_prewarmer']
tmp_ret = collect_all('onnxruntime.transformers')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['runtime_hooks/node_path_hook.py'],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='local-backend-pkg',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='local-backend-pkg',
)
app = BUNDLE(
    coll,
    name='local-backend-pkg.app',
    icon=None,
    bundle_identifier=None,
)
