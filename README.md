# HomeServer Ansible Playbooks

This repository contains Ansible playbooks and roles for managing a personal home server. It automates the setup and configuration of various services, containers, and essential system components.

## Features

- **Docker Management**: Automates Docker installation and container orchestration.
- **Neovim Setup**: Configures Neovim with custom settings and plugins.
- **Containerized Services**:
  - Vikunja
  - Jellyfin
  - Audiobookshelf
  - Homepage
- **System Configuration**:
  - Dotfiles management
  - Network setup
  - User configuration
- **Tailscale Integration**: Configures Tailscale for secure networking.

## Repository Structure

- **roles/**: Contains Ansible roles for specific tasks.
  - `docker`: Manages Docker installation and configuration.
  - `neovim`: Sets up Neovim.
  - `containers`: Manages containerized services.
  - `common`: Handles common system configurations.
- **group_vars/**: Contains group-specific variables.
- **inventory/**: Defines the inventory of managed hosts.
- **site.yml**: Main playbook to orchestrate all roles.
- **ansible.cfg**: Configuration file for Ansible.

