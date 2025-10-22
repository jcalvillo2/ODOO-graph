# Odoo Tracker

A powerful ETL (Extract, Transform, Load) tool for analyzing, tracking, and visualizing Odoo module dependencies, models, and views using Neo4j graph database.

## 🎯 Purpose

This tool helps Odoo developers understand complex codebases by:

- **Finding model definitions** across hundreds of modules
- **Analyzing module dependencies** and detecting circular references
- **Tracing inheritance chains** for models and views
- **Searching fields** across the entire codebase
- **Visualizing relationships** using graph queries

## 🚀 Features

- **Scalable**: Handles 500+ modules, 10,000+ models/views, 2GB+ codebases
- **Efficient**: Batch processing, streaming parsers, memory monitoring
- **Incremental**: Only re-index changed files
- **Fast**: Optional parallel processing, intelligent caching
- **User-friendly**: Rich CLI with progress bars and formatted output

## 🏗️ Architecture

```
Odoo Source Code
    ↓
AST/XML Parsers (streaming, cached)
    ↓
Batch Processing (memory-efficient)
    ↓
Neo4j Graph Database (indexed)
    ↓
CLI Queries (Cypher-powered)
```

## 📋 Prerequisites

- **Python 3.11+**
- **Docker & Docker Compose** (for Neo4j)
- **Git**

## 🔧 Installation

### 1. Clone the repository

```bash
git clone <repository-url>
cd ODOO-graph
```

### 2. Create virtual environment

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment

```bash
cp .env.example .env
# Edit .env with your settings
```

**Important settings in `.env`:**

- `NEO4J_PASSWORD`: Set a secure password
- `ADDONS_PATHS`: Comma-separated paths to your Odoo addons directories
- `BATCH_SIZE`: Adjust based on your system (default: 50)
- `MAX_MEMORY_PERCENT`: Memory usage limit (default: 70%)

### 5. Start Neo4j

```bash
docker-compose up -d
```

Verify Neo4j is running:
- Browser UI: http://localhost:7474
- Bolt connection: bolt://localhost:7687

## 📖 Usage

### View Configuration

```bash
python main.py config
```

### Index Odoo Modules

```bash
# Index all modules in a directory
python main.py index /path/to/odoo/addons

# Use custom batch size
python main.py index /path/to/odoo/addons --batch-size 100

# Incremental indexing (only changed files)
python main.py index /path/to/odoo/addons --incremental
```

### Query Dependencies

```bash
# Show module dependencies
python main.py dependencies sale

# Find where a model is defined
python main.py find-model res.partner

# List all models in a module
python main.py list-models sale
```

## 🗂️ Project Structure

```
/ODOO-graph/
├── cli/              # CLI commands (Click)
├── parsers/          # AST & XML parsers
├── graph/            # Neo4j integration
├── utils/            # Helpers (monitoring, hashing, logging)
├── config/           # Configuration management
├── tests/            # Test suite (Pytest)
├── main.py           # CLI entry point
├── requirements.txt  # Python dependencies
├── .env.example      # Environment variables template
├── docker-compose.yml # Neo4j setup
└── README.md         # This file
```

## 🧪 Development

### Run Tests

```bash
pytest
```

### Run Tests with Coverage

```bash
pytest --cov=. --cov-report=html
```

### Code Formatting

```bash
black .
```

### Linting

```bash
flake8
```

### Type Checking

```bash
mypy .
```

## 📊 Performance Targets

- Index **500 modules** in under 5 minutes
- Memory usage stays below **70%** of system RAM
- Incremental re-indexing in under 30 seconds
- Query response time under 1 second

## 🔍 How It Works

### 1. Extract

- Scans Odoo directories for modules
- Reads `__manifest__.py` files
- Parses Python files using AST
- Parses XML view files

### 2. Transform

- Extracts module metadata (name, version, dependencies)
- Identifies models (`_name`, `_inherit`, `_inherits`)
- Captures field definitions
- Processes view inheritance

### 3. Load

- Batch inserts into Neo4j
- Creates nodes: Module, Model, View
- Creates relationships: DEPENDS_ON, INHERITS_FROM, etc.
- Builds indexes for fast queries

## 🎓 Odoo Concepts

### Modules vs Models

- **Modules**: Odoo packages/addons (e.g., `sale`, `stock`)
- **Models**: Python classes representing database tables (e.g., `sale.order`, `res.partner`)

### Inheritance Types

- **`_inherit`**: Extends existing model
- **`_inherits`**: Delegates to another model

## 🛠️ Troubleshooting

### Neo4j won't start

```bash
# Check if port is already in use
docker ps

# Stop and remove containers
docker-compose down

# Start fresh
docker-compose up -d
```

### Out of memory errors

Reduce `BATCH_SIZE` in `.env`:

```
BATCH_SIZE=25
```

### Permission errors

Ensure the user has read access to Odoo source directories.

## 📚 Resources

- [Odoo Developer Documentation](https://www.odoo.com/documentation/)
- [Neo4j Cypher Manual](https://neo4j.com/docs/cypher-manual/current/)
- [Python AST Documentation](https://docs.python.org/3/library/ast.html)

## 🤝 Contributing

Contributions are welcome! Please:

1. Follow the THINK → PLAN → IMPLEMENT → VALIDATE methodology
2. Write all code in English
3. Add tests for new features
4. Update documentation

## 📝 License

[Add license information]

## 👥 Authors

[Add author information]

---

**Built with ❤️ for the Odoo community**
