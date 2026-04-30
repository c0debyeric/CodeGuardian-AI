#!/usr/bin/env python3
"""
LLM Gateway - Bootstrap Script
===============================
One script to rule them all. Takes you from zero to fully deployed on EKS.

Usage:
    python RUNME.py all --env dev        # Full bootstrap
    python RUNME.py preflight            # Check prerequisites
    python RUNME.py terraform --env dev  # Apply infrastructure
    python RUNME.py images               # Build and push Docker images
    python RUNME.py deploy               # Deploy to EKS via ArgoCD
    python RUNME.py validate             # Health checks
    python RUNME.py status               # Show current state
    python RUNME.py destroy --env dev    # Tear down everything
    python RUNME.py outputs              # Show terraform outputs
"""

import json
import os
import subprocess
import sys
import time
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

# Windows consoles default to cp1252 which can't encode emoji. Force UTF-8.
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")

try:
    import typer
    from rich.console import Console
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.table import Table
    from rich import print as rprint
except ImportError:
    print("Missing dependencies. Installing...")
    subprocess.run([sys.executable, "-m", "pip", "install", "typer[all]", "rich"], check=True)
    import typer
    from rich.console import Console
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.table import Table
    from rich import print as rprint

# =============================================================================
# Configuration
# =============================================================================

APP_NAME = "LLM Gateway"
PROJECT_ROOT = Path(__file__).parent.resolve()
TERRAFORM_DIR = PROJECT_ROOT / "terraform"
APP_DIR = PROJECT_ROOT / "app"
ARGOCD_DIR = PROJECT_ROOT / "argocd"
STATE_FILE = PROJECT_ROOT / ".bootstrap-state.json"
ENV_FILE = PROJECT_ROOT / ".env"

# GitHub repo URL
GITHUB_REPO_URL = "https://github.com/c0debyeric/CodeGuardian-AI"

console = Console()
app = typer.Typer(
    name="runme",
    help=f"✨ {APP_NAME} Bootstrap Script - Deploy from zero to production",
    add_completion=False,
)


# =============================================================================
# AWS Profile Handling
# =============================================================================
#
# We honor an explicit `--profile` (set on `all` / `terraform` / `images` / etc.)
# by exporting AWS_PROFILE into this process's environment. Every downstream
# tool we shell out to (awscli, terraform's aws provider, helm/kubectl via
# aws-iam-authenticator, docker login via `aws ecr get-login-password`) reads
# AWS_PROFILE, so this is the single hook we need.
#
# Region works the same way: AWS_REGION + AWS_DEFAULT_REGION cover the matrix
# of tools that pick one or the other.


def apply_aws_profile(profile: Optional[str], region: Optional[str] = None) -> None:
    """Set AWS_PROFILE / AWS_REGION env vars for this process and all children."""
    if profile:
        os.environ["AWS_PROFILE"] = profile
        os.environ.pop("AWS_ACCESS_KEY_ID", None)
        os.environ.pop("AWS_SECRET_ACCESS_KEY", None)
        os.environ.pop("AWS_SESSION_TOKEN", None)
    if region:
        os.environ["AWS_REGION"] = region
        os.environ["AWS_DEFAULT_REGION"] = region


class Environment(str, Enum):
    dev = "dev"
    prod = "prod"


class PhaseStatus(str, Enum):
    not_started = "not_started"
    in_progress = "in_progress"
    completed = "completed"
    failed = "failed"


# =============================================================================
# State Management
# =============================================================================


def load_state() -> dict:
    """Load bootstrap state from file."""
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {
        "phases": {},
        "env": None,
        "outputs": {},
        "last_run": None,
    }


def save_state(state: dict) -> None:
    """Save bootstrap state to file."""
    state["last_run"] = datetime.now().isoformat()
    STATE_FILE.write_text(json.dumps(state, indent=2))


def update_phase(phase: str, status: PhaseStatus, data: dict = None) -> None:
    """Update phase status in state."""
    state = load_state()
    state["phases"][phase] = {
        "status": status.value,
        "timestamp": datetime.now().isoformat(),
        "data": data or {},
    }
    save_state(state)


def get_phase_status(phase: str) -> Optional[str]:
    """Get status of a phase."""
    state = load_state()
    return state.get("phases", {}).get(phase, {}).get("status")


# =============================================================================
# Utility Functions
# =============================================================================


def run_command(
    cmd: list[str],
    cwd: Path = None,
    capture: bool = False,
    check: bool = True,
    env: dict = None,
) -> subprocess.CompletedProcess:
    """Run a shell command with nice output."""
    full_env = os.environ.copy()
    if env:
        full_env.update(env)
    
    if capture:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            env=full_env,
        )
    else:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            env=full_env,
        )
    
    if check and result.returncode != 0:
        if capture:
            console.print(f"[red]Error:[/red] {result.stderr}")
        raise typer.Exit(1)
    
    return result


def check_tool(name: str, version_cmd: list[str] = None) -> bool:
    """Check if a tool is installed."""
    try:
        cmd = version_cmd or [name, "--version"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.returncode == 0
    except FileNotFoundError:
        return False


def wait_for_condition(
    check_fn,
    message: str,
    timeout: int = 300,
    interval: int = 10,
) -> bool:
    """Wait for a condition to be true."""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task(message, total=None)
        start = time.time()
        while time.time() - start < timeout:
            if check_fn():
                return True
            time.sleep(interval)
        return False


def print_header(title: str) -> None:
    """Print a styled header."""
    console.print()
    console.print(Panel(f"[bold cyan]{title}[/bold cyan]", expand=False))
    console.print()


def print_success(message: str) -> None:
    """Print success message."""
    console.print(f"[green]✓[/green] {message}")


def print_error(message: str) -> None:
    """Print error message."""
    console.print(f"[red]✗[/red] {message}")


def print_warning(message: str) -> None:
    """Print warning message."""
    console.print(f"[yellow]![/yellow] {message}")


def print_info(message: str) -> None:
    """Print info message."""
    console.print(f"[blue]ℹ[/blue] {message}")


# =============================================================================
# Phase: Preflight Checks
# =============================================================================


def check_aws_credentials() -> tuple[bool, str]:
    """Check if AWS credentials are configured."""
    result = run_command(
        ["aws", "sts", "get-caller-identity", "--output", "json"],
        capture=True,
        check=False,
    )
    if result.returncode == 0:
        identity = json.loads(result.stdout)
        return True, identity.get("Arn", "Unknown")
    return False, result.stderr


def check_aws_region() -> tuple[bool, str]:
    """Check AWS region configuration."""
    result = run_command(
        ["aws", "configure", "get", "region"],
        capture=True,
        check=False,
    )
    if result.returncode == 0 and result.stdout.strip():
        return True, result.stdout.strip()
    # Check environment variable
    region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION")
    if region:
        return True, region
    return False, "No region configured"


@app.command()
def preflight(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed output"),
    profile: Optional[str] = typer.Option(None, "--profile", help="AWS CLI profile to use"),
    region: Optional[str] = typer.Option(None, "--region", help="AWS region (default: profile/env)"),
    skip_docker: bool = typer.Option(False, "--skip-docker", help="Don't require Docker (for infra-only flow)"),
) -> bool:
    """Check all prerequisites before deployment."""
    apply_aws_profile(profile, region)
    print_header("🔍 Preflight Checks")
    
    all_passed = True
    checks = []
    
    # Check required tools
    tools = [
        ("terraform", ["terraform", "version"]),
        ("aws", ["aws", "--version"]),
        ("kubectl", ["kubectl", "version", "--client"]),
        ("docker", ["docker", "--version"]),
        ("git", ["git", "--version"]),
    ]
    
    for tool_name, version_cmd in tools:
        if check_tool(tool_name, version_cmd):
            checks.append((tool_name, True, "Installed"))
        else:
            installed = False
            # Docker is optional when --skip-docker is passed
            if tool_name == "docker" and skip_docker:
                checks.append((tool_name, True, "Skipped (--skip-docker)"))
            else:
                checks.append((tool_name, False, "Not found"))
                all_passed = False
    
    # Check AWS credentials
    aws_ok, aws_info = check_aws_credentials()
    checks.append(("AWS Credentials", aws_ok, aws_info[:50] + "..." if len(aws_info) > 50 else aws_info))
    if not aws_ok:
        all_passed = False
    
    # Check AWS region
    region_ok, region_info = check_aws_region()
    checks.append(("AWS Region", region_ok, region_info))
    if not region_ok:
        all_passed = False
    
    # Check terraform files exist
    tf_files = ["main-caller.tf", "variables.tf", "versions.tf"]
    tf_ok = all((TERRAFORM_DIR / f).exists() for f in tf_files)
    checks.append(("Terraform files", tf_ok, str(TERRAFORM_DIR)))
    if not tf_ok:
        all_passed = False
    
    # Check app files exist
    backend_ok = (APP_DIR / "backend" / "Dockerfile").exists()
    admin_ui_ok = (APP_DIR / "admin-ui" / "Dockerfile").exists()
    checks.append(("Backend Dockerfile", backend_ok, str(APP_DIR / "backend")))
    checks.append(("Admin UI Dockerfile", admin_ui_ok, str(APP_DIR / "admin-ui")))
    if not backend_ok or not admin_ui_ok:
        all_passed = False
    
    # Display results
    table = Table(title="Preflight Check Results")
    table.add_column("Check", style="cyan")
    table.add_column("Status", style="bold")
    table.add_column("Details")
    
    for check_name, passed, details in checks:
        status = "[green]PASS[/green]" if passed else "[red]FAIL[/red]"
        table.add_row(check_name, status, details)
    
    console.print(table)
    
    if all_passed:
        print_success("All preflight checks passed!")
        update_phase("preflight", PhaseStatus.completed)
    else:
        print_error("Some preflight checks failed. Please fix the issues above.")
        update_phase("preflight", PhaseStatus.failed)
    
    return all_passed


# =============================================================================
# Phase: Terraform
# =============================================================================


def get_terraform_outputs() -> dict:
    """Get outputs from terraform."""
    result = run_command(
        ["terraform", "output", "-json"],
        cwd=TERRAFORM_DIR,
        capture=True,
        check=False,
    )
    if result.returncode == 0:
        outputs = json.loads(result.stdout)
        # Extract just the values
        return {k: v.get("value") for k, v in outputs.items()}
    return {}


def write_env_file(outputs: dict, env: str) -> None:
    """Write terraform outputs to .env file."""
    env_content = f"""# LLM Gateway - Environment Configuration
# Generated by RUNME.py on {datetime.now().isoformat()}
# Environment: {env}

# AWS Configuration
AWS_REGION={outputs.get('region', 'us-east-1')}

# EKS Cluster
EKS_CLUSTER_NAME={outputs.get('cluster_name', f'llm-gateway-{env}')}
EKS_CLUSTER_ENDPOINT={outputs.get('cluster_endpoint', '')}

# ECR Repositories
ECR_BACKEND_URI={outputs.get('ecr_backend_url', '')}
ECR_ADMIN_UI_URI={outputs.get('ecr_admin_ui_url', '')}

# RDS Database
RDS_ENDPOINT={outputs.get('rds_endpoint', '')}
RDS_PORT={outputs.get('rds_port', '5432')}
RDS_DATABASE={outputs.get('rds_database', 'gateway')}

# Domain
DOMAIN={outputs.get('domain', f'codeguardian.eric-n.com')}

# ArgoCD
ARGOCD_NAMESPACE=argocd

# Environment
ENVIRONMENT={env}
"""
    ENV_FILE.write_text(env_content)
    print_success(f"Environment file written to {ENV_FILE}")


@app.command()
def terraform(
    env: Environment = typer.Option(Environment.dev, "--env", "-e", help="Environment to deploy"),
    plan_only: bool = typer.Option(False, "--plan", help="Only show plan, don't apply"),
    auto_approve: bool = typer.Option(False, "--auto-approve", "-y", help="Skip confirmation"),
    destroy_flag: bool = typer.Option(False, "--destroy", help="Destroy infrastructure"),
    profile: Optional[str] = typer.Option(None, "--profile", help="AWS CLI profile to use"),
    region: Optional[str] = typer.Option(None, "--region", help="AWS region"),
) -> bool:
    """Apply Terraform infrastructure."""
    apply_aws_profile(profile, region)
    print_header(f"🏗️ Terraform {'Destroy' if destroy_flag else 'Apply'} - {env.value}")
    
    update_phase("terraform", PhaseStatus.in_progress)
    
    # Initialize terraform
    print_info("Initializing Terraform...")
    run_command(["terraform", "init", "-upgrade"], cwd=TERRAFORM_DIR)
    print_success("Terraform initialized")
    
    tfvars_file = TERRAFORM_DIR / "environments" / f"{env.value}.tfvars"
    if not tfvars_file.exists():
        print_error(f"Environment file not found: {tfvars_file}")
        update_phase("terraform", PhaseStatus.failed)
        return False
    
    # Plan
    print_info("Running Terraform plan...")
    plan_cmd = [
        "terraform", "plan",
        f"-var-file=environments/{env.value}.tfvars",
        "-out=tfplan",
    ]
    if destroy_flag:
        plan_cmd.append("-destroy")
    
    run_command(plan_cmd, cwd=TERRAFORM_DIR)
    
    if plan_only:
        print_info("Plan complete. Run without --plan to apply.")
        return True
    
    # Confirm
    if not auto_approve:
        confirm = typer.confirm(
            f"\n{'Destroy' if destroy_flag else 'Apply'} this plan?",
            default=False,
        )
        if not confirm:
            print_warning("Aborted by user")
            return False
    
    # Apply
    print_info(f"{'Destroying' if destroy_flag else 'Applying'} Terraform...")
    run_command(["terraform", "apply", "tfplan"], cwd=TERRAFORM_DIR)
    
    if destroy_flag:
        print_success("Infrastructure destroyed!")
        update_phase("terraform", PhaseStatus.not_started)
        # Clean up .env file
        if ENV_FILE.exists():
            ENV_FILE.unlink()
        return True
    
    # Get outputs and write to .env
    print_info("Capturing Terraform outputs...")
    outputs = get_terraform_outputs()
    
    if outputs:
        write_env_file(outputs, env.value)
        state = load_state()
        state["outputs"] = outputs
        state["env"] = env.value
        save_state(state)
        print_success("Terraform outputs captured")
    
    update_phase("terraform", PhaseStatus.completed, {"env": env.value})
    print_success("Terraform apply complete!")
    return True


# =============================================================================
# Phase: Kubeconfig
# =============================================================================


@app.command()
def kubeconfig(
    env: Environment = typer.Option(None, "--env", "-e", help="Environment"),
    profile: Optional[str] = typer.Option(None, "--profile", help="AWS CLI profile to use"),
    region: Optional[str] = typer.Option(None, "--region", help="AWS region"),
) -> bool:
    """Configure kubectl to access the EKS cluster."""
    apply_aws_profile(profile, region)
    print_header("🔐 Configuring Kubeconfig")
    
    # Get cluster name from state or env file
    state = load_state()
    cluster_name = state.get("outputs", {}).get("cluster_name")
    region = state.get("outputs", {}).get("region", "us-east-1")
    
    if not cluster_name:
        # Try to get from terraform outputs directly
        outputs = get_terraform_outputs()
        cluster_name = outputs.get("cluster_name")
        region = outputs.get("region", "us-east-1")
    
    if not cluster_name:
        env_val = env.value if env else state.get("env", "dev")
        cluster_name = f"llm-gateway-{env_val}"
        print_warning(f"Using default cluster name: {cluster_name}")
    
    print_info(f"Updating kubeconfig for cluster: {cluster_name}")
    
    result = run_command(
        ["aws", "eks", "update-kubeconfig", "--region", region, "--name", cluster_name],
        capture=True,
        check=False,
    )
    
    if result.returncode != 0:
        print_error(f"Failed to update kubeconfig: {result.stderr}")
        return False
    
    print_success("Kubeconfig updated")
    
    # Verify access
    print_info("Verifying cluster access...")
    result = run_command(
        ["kubectl", "get", "nodes", "-o", "wide"],
        capture=True,
        check=False,
    )
    
    if result.returncode == 0:
        print_success("Cluster access verified!")
        console.print(result.stdout)
        update_phase("kubeconfig", PhaseStatus.completed)
        return True
    else:
        print_error(f"Cannot access cluster: {result.stderr}")
        update_phase("kubeconfig", PhaseStatus.failed)
        return False


# =============================================================================
# Phase: Docker Images
# =============================================================================


@app.command()
def images(
    push: bool = typer.Option(True, "--push/--no-push", help="Push images to ECR"),
    tag: str = typer.Option(None, "--tag", "-t", help="Image tag (default: git SHA)"),
    profile: Optional[str] = typer.Option(None, "--profile", help="AWS CLI profile to use"),
    region: Optional[str] = typer.Option(None, "--region", help="AWS region"),
) -> bool:
    """Build and push Docker images to ECR."""
    apply_aws_profile(profile, region)
    print_header("🐳 Building Docker Images")
    
    update_phase("images", PhaseStatus.in_progress)
    
    # Get ECR URIs from state
    state = load_state()
    outputs = state.get("outputs", {})
    
    # If no outputs, try to get from terraform
    if not outputs.get("ecr_backend_url"):
        outputs = get_terraform_outputs()
    
    backend_uri = outputs.get("ecr_backend_url", "")
    admin_ui_uri = outputs.get("ecr_admin_ui_url", "")
    region = outputs.get("region", "us-east-1")
    
    if not backend_uri or not admin_ui_uri:
        print_error("ECR URIs not found. Run 'terraform' phase first.")
        update_phase("images", PhaseStatus.failed)
        return False
    
    # Get image tag
    if not tag:
        result = run_command(["git", "rev-parse", "--short", "HEAD"], capture=True)
        tag = result.stdout.strip() if result.returncode == 0 else "latest"
    
    print_info(f"Image tag: {tag}")
    
    # ECR Login
    print_info("Logging into ECR...")
    account_id = backend_uri.split(".")[0]
    ecr_url = f"{account_id}.dkr.ecr.{region}.amazonaws.com"
    
    login_result = run_command(
        ["aws", "ecr", "get-login-password", "--region", region],
        capture=True,
    )
    
    docker_login = subprocess.run(
        ["docker", "login", "--username", "AWS", "--password-stdin", ecr_url],
        input=login_result.stdout,
        capture_output=True,
        text=True,
    )
    
    if docker_login.returncode != 0:
        print_error(f"ECR login failed: {docker_login.stderr}")
        return False
    
    print_success("ECR login successful")
    
    # Build and push backend
    print_info("Building backend image...")
    backend_dir = APP_DIR / "backend"
    run_command(
        ["docker", "build", "-t", f"{backend_uri}:{tag}", "-t", f"{backend_uri}:latest", "."],
        cwd=backend_dir,
    )
    print_success("Backend image built")
    
    # Build and push admin-ui (Next.js)
    print_info("Building admin-ui image...")
    admin_ui_dir = APP_DIR / "admin-ui"
    run_command(
        ["docker", "build", "-t", f"{admin_ui_uri}:{tag}", "-t", f"{admin_ui_uri}:latest", "."],
        cwd=admin_ui_dir,
    )
    print_success("Admin UI image built")
    
    if push:
        print_info("Pushing backend image to ECR...")
        run_command(["docker", "push", f"{backend_uri}:{tag}"])
        run_command(["docker", "push", f"{backend_uri}:latest"])
        print_success("Backend image pushed")
        
        print_info("Pushing admin-ui image to ECR...")
        run_command(["docker", "push", f"{admin_ui_uri}:{tag}"])
        run_command(["docker", "push", f"{admin_ui_uri}:latest"])
        print_success("Admin UI image pushed")
    
    update_phase("images", PhaseStatus.completed, {"tag": tag})
    print_success(f"Images ready with tag: {tag}")
    return True


# =============================================================================
# Phase: Deploy (ArgoCD)
# =============================================================================


def update_argocd_repo_url(repo_url: str) -> None:
    """Update the repository URL in ArgoCD root-app.yaml."""
    root_app_path = ARGOCD_DIR / "root-app.yaml"
    
    if not root_app_path.exists():
        print_warning(f"ArgoCD root-app.yaml not found at {root_app_path}")
        return
    
    content = root_app_path.read_text()
    
    # Replace placeholder or existing URL
    import re
    pattern = r"repoURL:\s*https://github\.com/[^\s]+"
    replacement = f"repoURL: {repo_url}"
    
    new_content = re.sub(pattern, replacement, content)
    
    if new_content != content:
        root_app_path.write_text(new_content)
        print_success(f"Updated ArgoCD repo URL to: {repo_url}")
    else:
        print_info("ArgoCD repo URL already set correctly")


def wait_for_argocd() -> bool:
    """Wait for ArgoCD to be ready."""
    def check():
        result = run_command(
            ["kubectl", "get", "pods", "-n", "argocd", "-l", "app.kubernetes.io/name=argocd-server", "-o", "jsonpath={.items[0].status.phase}"],
            capture=True,
            check=False,
        )
        return result.returncode == 0 and "Running" in result.stdout
    
    return wait_for_condition(check, "Waiting for ArgoCD to be ready...", timeout=300)


def get_argocd_password() -> str:
    """Get ArgoCD admin password."""
    result = run_command(
        ["kubectl", "-n", "argocd", "get", "secret", "argocd-initial-admin-secret", "-o", "jsonpath={.data.password}"],
        capture=True,
        check=False,
    )
    
    if result.returncode == 0:
        import base64
        return base64.b64decode(result.stdout).decode("utf-8")
    return ""


def create_argocd_repo_secret(repo_url: str) -> None:
    """Create ArgoCD repository credential secret for GitHub access.
    
    Uses `gh auth token` to get a GitHub token. If gh CLI is not available
    or not authenticated, prompts the user for a token.
    Idempotent: updates the secret if it already exists.
    """
    print_info("Configuring ArgoCD repository credentials...")
    
    # Check if the secret already exists
    result = run_command(
        ["kubectl", "get", "secret", "github-repo-creds", "-n", "argocd"],
        capture=True,
        check=False,
    )
    if result.returncode == 0:
        print_success("ArgoCD repo secret already exists")
        return
    
    # Try to get token from gh CLI
    token = None
    result = run_command(["gh", "auth", "token"], capture=True, check=False)
    if result.returncode == 0 and result.stdout.strip():
        token = result.stdout.strip()
        print_success("GitHub token obtained from gh CLI")
    else:
        # Prompt user
        token = typer.prompt(
            "GitHub PAT for ArgoCD repo access (needs 'repo' scope)",
            hide_input=True,
        )
    
    if not token:
        print_warning("No GitHub token provided. ArgoCD may fail to sync private repos.")
        return
    
    # Get GitHub username from gh CLI or prompt
    username = "git"  # GitHub accepts 'git' as username with PAT
    
    # Create the secret
    run_command(
        [
            "kubectl", "create", "secret", "generic", "github-repo-creds",
            "-n", "argocd",
            f"--from-literal=type=git",
            f"--from-literal=url={repo_url}",
            f"--from-literal=username={username}",
            f"--from-literal=password={token}",
        ],
        capture=True,
    )
    
    # Label it as an ArgoCD repo secret
    run_command(
        [
            "kubectl", "label", "secret", "github-repo-creds",
            "-n", "argocd",
            "argocd.argoproj.io/secret-type=repository",
        ],
        capture=True,
    )
    
    print_success("ArgoCD repo credential secret created")


@app.command()
def deploy(
    repo_url: str = typer.Option(None, "--repo", help="GitHub repository URL"),
    skip_argocd_wait: bool = typer.Option(False, "--skip-wait", help="Skip waiting for ArgoCD"),
) -> bool:
    """Deploy application via ArgoCD."""
    print_header("🚀 Deploying via ArgoCD")
    
    update_phase("deploy", PhaseStatus.in_progress)
    
    # Update ArgoCD repo URL if provided
    final_repo_url = repo_url or GITHUB_REPO_URL
    if "YOUR_USERNAME" in final_repo_url:
        final_repo_url = typer.prompt("Enter your GitHub repository URL")
    
    update_argocd_repo_url(final_repo_url)
    
    # Wait for ArgoCD
    if not skip_argocd_wait:
        print_info("Waiting for ArgoCD to be ready...")
        if not wait_for_argocd():
            print_error("ArgoCD not ready after timeout")
            update_phase("deploy", PhaseStatus.failed)
            return False
        print_success("ArgoCD is ready!")
    
    # Create ArgoCD repo secret for GitHub access (idempotent)
    create_argocd_repo_secret(final_repo_url)
    
    # Get ArgoCD password
    password = get_argocd_password()
    if password:
        print_info(f"ArgoCD admin password: {password}")
    
    # Apply root application
    root_app_path = ARGOCD_DIR / "root-app.yaml"
    if root_app_path.exists():
        print_info("Applying ArgoCD root application...")
        run_command(["kubectl", "apply", "-f", str(root_app_path)])
        print_success("Root application applied!")
    else:
        print_warning("root-app.yaml not found, skipping")
    
    # Show ArgoCD access info
    print_info("Getting ArgoCD server address...")
    result = run_command(
        ["kubectl", "get", "svc", "-n", "argocd", "argocd-server", "-o", "jsonpath={.status.loadBalancer.ingress[0].hostname}"],
        capture=True,
        check=False,
    )
    
    if result.returncode == 0 and result.stdout:
        console.print()
        console.print(Panel(
            f"[bold green]ArgoCD UI[/bold green]\n\n"
            f"URL: https://{result.stdout}\n"
            f"Username: admin\n"
            f"Password: {password}",
            title="Access Information",
        ))
    else:
        print_info("ArgoCD LoadBalancer not ready yet. Use port-forward:")
        print_info("kubectl port-forward svc/argocd-server -n argocd 8080:443")
    
    update_phase("deploy", PhaseStatus.completed)
    print_success("Deployment initiated!")
    return True


# =============================================================================
# Phase: Validate
# =============================================================================


@app.command()
def validate() -> bool:
    """Validate the deployment is healthy."""
    print_header("✅ Validating Deployment")
    
    checks = []
    
    # Check nodes
    print_info("Checking EKS nodes...")
    result = run_command(
        ["kubectl", "get", "nodes", "-o", "jsonpath={.items[*].status.conditions[?(@.type=='Ready')].status}"],
        capture=True,
        check=False,
    )
    nodes_ready = result.returncode == 0 and "True" in result.stdout
    checks.append(("EKS Nodes Ready", nodes_ready))
    
    # Check ArgoCD
    print_info("Checking ArgoCD...")
    result = run_command(
        ["kubectl", "get", "pods", "-n", "argocd", "-l", "app.kubernetes.io/part-of=argocd", "--no-headers"],
        capture=True,
        check=False,
    )
    argocd_ok = result.returncode == 0 and len(result.stdout.strip().split("\n")) > 0
    checks.append(("ArgoCD Running", argocd_ok))
    
    # Check monitoring namespace
    print_info("Checking monitoring stack...")
    result = run_command(
        ["kubectl", "get", "namespace", "monitoring", "-o", "name"],
        capture=True,
        check=False,
    )
    monitoring_ok = result.returncode == 0
    checks.append(("Monitoring Namespace", monitoring_ok))
    
    # Check if CodeGuardian namespace exists
    print_info("Checking CodeGuardian namespace...")
    result = run_command(
        ["kubectl", "get", "namespace", "codeguardian", "-o", "name"],
        capture=True,
        check=False,
    )
    app_ns_ok = result.returncode == 0
    checks.append(("CodeGuardian Namespace", app_ns_ok))
    
    # Check CodeGuardian pods if namespace exists
    if app_ns_ok:
        result = run_command(
            ["kubectl", "get", "pods", "-n", "codeguardian", "--no-headers"],
            capture=True,
            check=False,
        )
        app_pods_ok = result.returncode == 0 and "Running" in result.stdout
        checks.append(("CodeGuardian Pods", app_pods_ok))
    
    # Display results
    table = Table(title="Validation Results")
    table.add_column("Component", style="cyan")
    table.add_column("Status", style="bold")
    
    all_ok = True
    for check_name, passed in checks:
        status = "[green]✓ HEALTHY[/green]" if passed else "[red]✗ UNHEALTHY[/red]"
        table.add_row(check_name, status)
        if not passed:
            all_ok = False
    
    console.print(table)
    
    if all_ok:
        print_success("All validation checks passed!")
        update_phase("validate", PhaseStatus.completed)
    else:
        print_warning("Some components are not healthy yet.")
        update_phase("validate", PhaseStatus.failed)
    
    return all_ok


# =============================================================================
# Phase: Status
# =============================================================================


@app.command()
def status() -> None:
    """Show current bootstrap status."""
    print_header("📊 Bootstrap Status")
    
    state = load_state()
    
    # Environment info
    console.print(f"[bold]Environment:[/bold] {state.get('env', 'Not set')}")
    console.print(f"[bold]Last Run:[/bold] {state.get('last_run', 'Never')}")
    console.print()
    
    # Phase status table
    table = Table(title="Phase Status")
    table.add_column("Phase", style="cyan")
    table.add_column("Status", style="bold")
    table.add_column("Timestamp")
    
    phases = [
        "preflight", "terraform", "kubeconfig", "images", "deploy", "validate"
    ]
    
    for phase in phases:
        phase_data = state.get("phases", {}).get(phase, {})
        status_val = phase_data.get("status", "not_started")
        timestamp = phase_data.get("timestamp", "-")
        
        if status_val == "completed":
            status_str = "[green]✓ Completed[/green]"
        elif status_val == "in_progress":
            status_str = "[yellow]⟳ In Progress[/yellow]"
        elif status_val == "failed":
            status_str = "[red]✗ Failed[/red]"
        else:
            status_str = "[dim]○ Not Started[/dim]"
        
        table.add_row(phase.capitalize(), status_str, timestamp[:19] if timestamp != "-" else "-")
    
    console.print(table)
    
    # Show outputs if available
    outputs = state.get("outputs", {})
    if outputs:
        console.print()
        console.print("[bold]Terraform Outputs:[/bold]")
        for key, value in outputs.items():
            if value and not key.endswith("_arn"):  # Skip ARNs for cleaner output
                console.print(f"  {key}: {value}")


# =============================================================================
# Phase: Outputs
# =============================================================================


@app.command()
def outputs(
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
    refresh: bool = typer.Option(False, "--refresh", "-r", help="Refresh from Terraform"),
) -> None:
    """Show or refresh Terraform outputs."""
    print_header("📤 Terraform Outputs")
    
    if refresh:
        print_info("Refreshing outputs from Terraform...")
        tf_outputs = get_terraform_outputs()
        if tf_outputs:
            state = load_state()
            state["outputs"] = tf_outputs
            save_state(state)
            print_success("Outputs refreshed")
    
    state = load_state()
    outputs_data = state.get("outputs", {})
    
    if not outputs_data:
        outputs_data = get_terraform_outputs()
    
    if json_output:
        console.print(json.dumps(outputs_data, indent=2))
    else:
        if outputs_data:
            table = Table(title="Outputs")
            table.add_column("Key", style="cyan")
            table.add_column("Value")
            
            for key, value in sorted(outputs_data.items()):
                # Truncate long values
                str_val = str(value)
                if len(str_val) > 60:
                    str_val = str_val[:57] + "..."
                table.add_row(key, str_val)
            
            console.print(table)
        else:
            print_warning("No outputs available. Run 'terraform' first.")


# =============================================================================
# Phase: Destroy
# =============================================================================


@app.command()
def destroy(
    env: Environment = typer.Option(..., "--env", "-e", help="Environment to destroy"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
) -> bool:
    """Destroy all infrastructure."""
    print_header(f"💥 Destroying Infrastructure - {env.value}")
    
    if not force:
        console.print("[bold red]WARNING: This will destroy ALL infrastructure![/bold red]")
        console.print(f"Environment: {env.value}")
        confirm = typer.confirm("Are you SURE you want to destroy everything?", default=False)
        if not confirm:
            print_warning("Aborted by user")
            return False
        
        # Double confirm for production
        if env == Environment.prod:
            confirm2 = typer.prompt("Type 'destroy-prod' to confirm production destruction")
            if confirm2 != "destroy-prod":
                print_warning("Aborted - confirmation text did not match")
                return False
    
    return terraform(env=env, auto_approve=True, destroy_flag=True)


# =============================================================================
# Full Bootstrap: All Phases
# =============================================================================


@app.command("all")
def run_all(
    env: Environment = typer.Option(Environment.dev, "--env", "-e", help="Environment to deploy"),
    skip_confirmations: bool = typer.Option(False, "--yes", "-y", help="Skip all confirmations"),
    repo_url: str = typer.Option(None, "--repo", help="GitHub repository URL"),
    profile: Optional[str] = typer.Option(None, "--profile", help="AWS CLI profile to use"),
    region: Optional[str] = typer.Option("us-east-1", "--region", help="AWS region"),
    skip_images: bool = typer.Option(False, "--skip-images", help="Skip docker build/push (deploy infra + ArgoCD only)"),
) -> None:
    """Run complete bootstrap from scratch."""
    apply_aws_profile(profile, region)
    console.print(Panel(
        f"[bold cyan]🛡️ {APP_NAME} - Full Bootstrap[/bold cyan]\n\n"
        f"Environment: {env.value}\n"
        f"This will:\n"
        f"  1. Check prerequisites\n"
        f"  2. Apply Terraform infrastructure\n"
        f"  3. Configure kubectl\n"
        f"  4. Build and push Docker images\n"
        f"  5. Deploy via ArgoCD\n"
        f"  6. Validate deployment",
        expand=False,
    ))
    
    if not skip_confirmations:
        if not typer.confirm("\nProceed with full bootstrap?", default=True):
            print_warning("Aborted by user")
            raise typer.Exit(0)
    
    # Phase 1: Preflight
    console.print("\n" + "=" * 60)
    if not preflight(verbose=False, profile=None, region=None, skip_docker=skip_images):
        print_error("Preflight checks failed. Fix issues and try again.")
        raise typer.Exit(1)
    
    # Phase 2: Terraform
    console.print("\n" + "=" * 60)
    if not terraform(env=env, plan_only=False, auto_approve=skip_confirmations, destroy_flag=False, profile=None, region=None):
        print_error("Terraform failed.")
        raise typer.Exit(1)
    
    # Phase 3: Kubeconfig
    console.print("\n" + "=" * 60)
    if not kubeconfig(env=env, profile=None, region=None):
        print_error("Kubeconfig setup failed.")
        raise typer.Exit(1)
    
    # Phase 4: Docker Images (optional)
    if skip_images:
        console.print("\n" + "=" * 60)
        print_warning("Skipping image build/push (--skip-images). Pods will be ImagePullBackOff until CI pushes images.")
    else:
        console.print("\n" + "=" * 60)
        if not images(push=True, tag=None, profile=None, region=None):
            print_error("Image build/push failed.")
            raise typer.Exit(1)
    
    # Phase 5: Deploy
    console.print("\n" + "=" * 60)
    final_repo = repo_url or GITHUB_REPO_URL
    if "YOUR_USERNAME" in final_repo and not skip_confirmations:
        final_repo = typer.prompt("Enter your GitHub repository URL")
    
    if not deploy(repo_url=final_repo, skip_argocd_wait=False):
        print_error("Deployment failed.")
        raise typer.Exit(1)
    
    # Phase 6: Validate
    console.print("\n" + "=" * 60)
    validate()
    
    # Final summary
    console.print("\n" + "=" * 60)
    console.print(Panel(
        f"[bold green]🎉 Bootstrap Complete![/bold green]\n\n"
        f"Environment: {env.value}\n\n"
        f"Next steps:\n"
        f"  • Access ArgoCD UI to monitor deployments\n"
        f"  • Check Grafana for metrics and dashboards\n"
        f"  • Test the CodeGuardian API\n\n"
        f"Run [cyan]python RUNME.py status[/cyan] to see current state\n"
        f"Run [cyan]python RUNME.py validate[/cyan] to check health",
        title="✅ Success",
        expand=False,
    ))


# =============================================================================
# Entry Point
# =============================================================================

if __name__ == "__main__":
    app()