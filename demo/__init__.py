"""The offline demo: the real team on one requirement, with a simulated model and sandbox.

``python -m demo`` runs the actual PM, Coder and QA agents, the LangGraph team graph, the
A2A broker and the MCP file server. Only the parts that cost money or need Docker are
simulated: model replies come from ``demo.script``, and programs and tests "run" in
``demo.sandbox``. Every line it prints says so. It needs no API key, no Docker and no
network.
"""
