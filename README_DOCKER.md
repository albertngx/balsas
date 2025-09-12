# Docker Usage Guide for Salina Simulation

This guide explains how to run the Salina evaporation pond simulation using Docker.

## Quick Start

### 1. Build and Run (Simple)
```bash
# Build and run the simulation
docker-compose up --build salina-simulation

# Run in background
docker-compose up -d --build salina-simulation

# View logs
docker-compose logs -f salina-simulation
```

### 2. Available Services

#### Standard Simulation
```bash
docker-compose --profile simulation up --build
```

#### Development Mode (Interactive)
```bash
# Start interactive development container
docker-compose --profile dev up --build salina-dev

# Inside the container:
python -m src.run
python -m src.run --plot
```

#### With Plot Display (Linux with X11)
```bash
# Allow X11 forwarding
xhost +local:docker

# Run with plots
docker-compose --profile plots up --build salina-with-plots
```

## Docker Commands

### Build the Image
```bash
docker build -t salina-simulation .
```

### Run Directly
```bash
# Basic run
docker run --rm -v $(pwd)/experiment_results:/app/experiment_results salina-simulation

# With custom arguments
docker run --rm -v $(pwd)/experiment_results:/app/experiment_results salina-simulation python -m src.run --plot

# Interactive mode
docker run --rm -it -v $(pwd):/app salina-simulation /bin/bash
```

## Volume Mounts

The Docker setup mounts these directories:

- `./experiment_results` → `/app/experiment_results` (Results persist on host)
- `./inputs` → `/app/inputs` (Read-only input data)
- `./env.yaml` → `/app/env.yaml` (Read-only configuration)

## Environment Variables

You can customize behavior with environment variables:

```bash
# Custom Python settings
docker-compose run -e PYTHONPATH=/custom/path salina-simulation

# For debugging
docker-compose run -e PYTHONUNBUFFERED=1 salina-simulation
```

## Configuration

### Custom Configuration
```bash
# Use different config file
docker run --rm \
  -v $(pwd)/experiment_results:/app/experiment_results \
  -v $(pwd)/custom_env.yaml:/app/env.yaml:ro \
  salina-simulation
```

### Custom Input Data
```bash
# Use different input directory
docker run --rm \
  -v $(pwd)/experiment_results:/app/experiment_results \
  -v $(pwd)/custom_inputs:/app/inputs:ro \
  salina-simulation
```

## Troubleshooting

### Permission Issues
```bash
# Fix ownership of results
sudo chown -R $USER:$USER experiment_results/
```

### Plot Display Issues (Linux)
```bash
# Enable X11 forwarding
xhost +local:docker

# Or use VNC/web-based plotting (future enhancement)
```

### Memory Issues
```bash
# Limit memory usage
docker run --rm --memory=2g -v $(pwd)/experiment_results:/app/experiment_results salina-simulation
```

### Debug Container
```bash
# Start container and examine
docker-compose run --rm salina-dev /bin/bash

# Inside container:
ls -la
python --version
python -c "import pandas, yaml, matplotlib; print('Dependencies OK')"
```

## Production Deployment

### Using Docker Swarm
```bash
docker stack deploy -c docker-compose.yml salina-stack
```

### Using Kubernetes
Convert the compose file:
```bash
kompose convert -f docker-compose.yml
kubectl apply -f .
```

## Image Information

- **Base**: Python 3.10 slim
- **Size**: ~200MB (optimized multi-stage build)
- **User**: Non-root `salina` user for security
- **Health Check**: Validates Python dependencies
- **Dependencies**: pandas, pyyaml, matplotlib, numpy

## Examples

### Batch Processing
```bash
# Process multiple configurations
for config in configs/*.yaml; do
    docker run --rm \
        -v $(pwd)/experiment_results:/app/experiment_results \
        -v "$config":/app/env.yaml:ro \
        salina-simulation
done
```

### CI/CD Integration
```yaml
# .github/workflows/simulation.yml
- name: Run Simulation
  run: |
    docker-compose up --build salina-simulation
    # Upload results as artifacts
```

This Docker setup provides a consistent, reproducible environment for running the salina simulation across different systems.
