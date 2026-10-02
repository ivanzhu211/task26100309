#!/bin/sh
# BranchForge 测试执行命令
exec python3 -m pytest tests/ -q "$@"
