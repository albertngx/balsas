# Salina Evaporation Pond Simulation
# Multi-stage build for optimal image size

FROM python:3.10-slim as builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    gfortran \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --user -r requirements.txt

# Production stage
FROM python:3.10-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    libgfortran5 \
    && rm -rf /var/lib/apt/lists/*

# Copy Python packages from builder
COPY --from=builder /root/.local /root/.local

# Make sure scripts in .local are usable
ENV PATH=/root/.local/bin:$PATH

# Set working directory
WORKDIR /app

# Copy the application code
COPY src/ src/
COPY inputs/ inputs/
COPY phreeqc-3.5.0-14000/ phreeqc-3.5.0-14000/
COPY env.yaml .
COPY requirements.txt .

# Make PHREEQC executable
RUN chmod +x phreeqc-3.5.0-14000/bin/phreeqc

# Create output directory
RUN mkdir -p experiment_results

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Create a non-root user for security
RUN useradd --create-home --shell /bin/bash salina
RUN chown -R salina:salina /app
USER salina

# Expose port for potential web interface (future use)
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import pandas, yaml, matplotlib; print('OK')" || exit 1

# Default command
CMD ["python", "-m", "src.run"]
