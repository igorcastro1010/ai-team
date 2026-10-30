"""Fail closed on effective Hermes tools, including MCP omitted by REST inventory."""

import sys
import urllib.request


def validate_policy(config, effective_toolsets, effective_cron_toolsets):
    return (
        config.get("platform_toolsets", {}).get("api_server") == []
        and config.get("platform_toolsets", {}).get("cron") == []
        and not config.get("mcp_servers")
        and not effective_toolsets
        and not effective_cron_toolsets
    )


def main():
    try:
        from hermes_cli.config import load_config
        from hermes_cli.tools_config import _get_platform_tools

        config = load_config()
        # Unlike REST /v1/toolsets, include default MCP in the runtime resolution.
        tools = _get_platform_tools(
            config, "api_server", include_default_mcp_servers=True
        )
        cron_tools = _get_platform_tools(
            config, "cron", include_default_mcp_servers=True
        )
        if not validate_policy(config, tools, cron_tools):
            raise RuntimeError("policy mismatch")
        with urllib.request.urlopen(
            "http://127.0.0.1:8642/health", timeout=3
        ) as response:
            if response.status != 200:
                raise RuntimeError("gateway unavailable")
    except Exception:  # noqa: BLE001 - health logs must not disclose config/provider secrets
        print("Hermes health/policy check failed", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
