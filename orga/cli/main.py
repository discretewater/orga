import typer
import asyncio
import json
import yaml
from pathlib import Path
from typing import Optional, List
from pydantic import ValidationError

from orga.pipeline import OrgaPipeline
from orga.model import OrgaConfig
from orga.registry import registry

# Ensure all default strategies are registered
import orga.fetch.httpx_fetcher
import orga.discover
import orga.parse.fields.parsers
import orga.parse.fields.classifier
import orga.merge.processor

app = typer.Typer(help="ORGA - Organization Profile Extractor CLI")

def load_config(config_path: Optional[Path]) -> OrgaConfig:
    """
    Load OrgaConfig from a YAML or JSON file.
    """
    if config_path is None:
        return OrgaConfig()
    
    if not config_path.exists():
        typer.secho(f"Error: Config file {config_path} not found.", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)
    
    try:
        content = config_path.read_text(encoding="utf-8")
        if config_path.suffix in [".yaml", ".yml"]:
            data = yaml.safe_load(content)
        else:
            data = json.loads(content)
        
        return OrgaConfig.model_validate(data or {})
    except ValidationError as e:
        typer.secho(f"Error: Invalid configuration in {config_path}:", fg=typer.colors.RED, err=True)
        typer.echo(str(e), err=True)
        raise typer.Exit(code=1)
    except Exception as e:
        typer.secho(f"Error loading config: {str(e)}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

@app.command()
def parse(
    url: str = typer.Argument(..., help="The URL to parse"),
    config: Optional[Path] = typer.Option(None, "--config", "-c", help="Path to configuration file (YAML/JSON)"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Path to save the output JSON"),
    pretty: bool = typer.Option(True, help="Pretty print JSON output"),
    debug: bool = typer.Option(False, "--debug", "-d", help="Enable debug output (internal evidence, filtered links)")
):
    """
    Parse an organization profile from a single URL.
    """
    orga_config = load_config(config)
    pipeline = OrgaPipeline(orga_config)
    
    async def _run():
        typer.echo(f"Fetching and parsing: {url} ...", err=True)
        profile = await pipeline.run_from_url(url)
        return profile

    profile = asyncio.run(_run())
    
    indent = 2 if pretty else None
    
    # Configure export based on debug flag
    exclude_fields = {}
    if not debug:
        # Hide internal/rejected evidence and debug info in standard mode
        exclude_fields = {"internal_evidence", "debug_info"}
        
    # We use model_dump then json.dumps because model_dump_json doesn't support complex exclude logic as easily with nested models 
    # (actually it does, but manual control is safer here). 
    # Wait, model_dump_json supports `exclude`.
    # However, `internal_evidence` is also inside `Contact` and `Location`. 
    # We need to exclude it recursively. Pydantic excludes are usually recursive if field names match.
    
    # Pydantic v2 recursive exclusion:
    # exclude={"internal_evidence", "debug_info", "phones": {"__all__": {"internal_evidence"}}, ...}
    # This is getting complicated.
    # Simpler: If we defined `internal_evidence` in models, we can just pass `exclude` if it works recursively.
    # Or, we update the models to use `Field(exclude=True)`? No, that's permanent.
    
    # Let's try explicit recursive exclusion for top-level + common nested fields
    if not debug:
        exclude_set = {
            "internal_evidence": True,
            "debug_info": True,
            "locations": {"__all__": {"internal_evidence": True}},
            "phones": {"__all__": {"internal_evidence": True}},
            "emails": {"__all__": {"internal_evidence": True}},
            "social_links": {"__all__": {"internal_evidence": True}}
        }
        json_output = profile.model_dump_json(indent=indent, exclude=exclude_set)
    else:
        json_output = profile.model_dump_json(indent=indent)
    
    if output:
        output.write_text(json_output, encoding="utf-8")
        typer.echo(f"Saved output to {output}", err=True)
    else:
        typer.echo(json_output)

@app.command()
def parse_batch(
    input_file: Path = typer.Argument(..., help="Text file containing URLs (one per line)"),
    config: Optional[Path] = typer.Option(None, "--config", "-c", help="Path to configuration file"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Path to save the output JSONL file"),
    pretty: bool = typer.Option(False, "--pretty", help="Pretty print JSON output (best for stdout debugging)"),
    debug: bool = typer.Option(False, "--debug", "-d", help="Enable debug output in JSONL")
):
    """
    Batch parse multiple URLs.
    Default output is JSONL (one JSON per line).
    Use --pretty for readable output on stdout.
    """
    orga_config = load_config(config)
    pipeline = OrgaPipeline(orga_config)
    
    if not input_file.exists():
        typer.secho(f"Error: Input file {input_file} not found.", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)
    
    urls = [line.strip() for line in input_file.read_text().splitlines() if line.strip()]
    
    async def _run_batch():
        results = []
        for i, url in enumerate(urls):
            # Log progress to stderr so stdout remains clean for piping
            typer.echo(f"[{i+1}/{len(urls)}] Processing {url}...", err=True)
            try:
                profile = await pipeline.run_from_url(url)
                
                # Determine exclusion set
                exclude_set = {}
                if not debug:
                    exclude_set = {
                        "internal_evidence": True,
                        "debug_info": True,
                        "locations": {"__all__": {"internal_evidence": True}},
                        "phones": {"__all__": {"internal_evidence": True}},
                        "emails": {"__all__": {"internal_evidence": True}},
                        "social_links": {"__all__": {"internal_evidence": True}}
                    }
                
                # Format output
                indent = 2 if pretty and not output else None
                json_str = profile.model_dump_json(indent=indent, exclude=exclude_set if not debug else None)
                results.append(json_str)
                    
            except Exception as e:
                typer.secho(f"Failed to process {url}: {str(e)}", fg=typer.colors.YELLOW, err=True)
        return results

    json_lines = asyncio.run(_run_batch())
    
    if output:
        # File output is always JSONL (no pretty print to ensure validity)
        if pretty:
             typer.secho("Warning: --pretty is ignored when writing to file to maintain valid JSONL format.", fg=typer.colors.YELLOW, err=True)
        
        with output.open("w", encoding="utf-8") as f:
            for line in json_lines:
                # If we computed pretty strings above, we must flatten them for JSONL file
                if pretty:
                    # Parse back and dump as single line
                    import json
                    line = json.dumps(json.loads(line))
                f.write(line + "\n")
        typer.secho(f"Successfully processed {len(json_lines)} URLs. Output: {output}", fg=typer.colors.GREEN, err=True)
    else:
        # Stdout output
        for line in json_lines:
            typer.echo(line)

@app.command()
def list_strategies():
    """
    List all registered strategies.
    """
    kinds = ["fetcher", "discoverer", "parser", "category_classifier", "merger"]
    
    typer.echo("Registered ORGA Strategies:")
    for kind in kinds:
        strategies = registry.list(kind)
        typer.echo(f"\n[{kind.upper()}]")
        if not strategies:
            typer.echo("  (None)")
        for name in strategies:
            impl = registry.get(kind, name)
            typer.echo(f"  - {name}: {impl.__name__}")

@app.command()
def validate_config(config_path: Path):
    """
    Validate an ORGA configuration file.
    """
    load_config(config_path)
    typer.secho(f"Configuration is valid: {config_path}", fg=typer.colors.GREEN)

@app.command()
def inspect_signals(url: str):
    """
    Inspect raw signals extracted from a URL (Debug mode).
    """
    typer.echo(f"Inspecting signals for {url}...")
    typer.echo("This feature is planned for a future milestone (M4).", err=True)

if __name__ == "__main__":
    app()
