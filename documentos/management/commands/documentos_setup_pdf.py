"""
Sugestão (e execução opcional) de instalação de dependências PDF — apenas em terminal explícito.

Nunca é invocado automaticamente por requests HTTP.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Mostra ou executa comandos típicos para instalar motores PDF (LibreOffice, pacotes Python)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Apenas lista os comandos que seriam executados.",
        )
        parser.add_argument(
            "--yes",
            action="store_true",
            help="Executa os comandos (pode alterar o sistema).",
        )
        parser.add_argument(
            "--engine",
            choices=("libreoffice", "word_com", "auto"),
            default="auto",
            help="Foco da instalação de sistema (LibreOffice vs Word/pywin32).",
        )
        parser.add_argument(
            "--python-only",
            action="store_true",
            help="Apenas pacotes pip (docxtpl, python-docx, docx2pdf/pywin32 no Windows).",
        )

    def handle(self, *args, **options):
        dry: bool = options["dry_run"]
        yes: bool = options["yes"]
        engine: str = options["engine"]
        python_only: bool = options["python_only"]

        pip_base = [sys.executable, "-m", "pip", "install", "docxtpl", "python-docx"]
        pip_cmds: list[list[str]] = [pip_base]
        if os.name == "nt" and engine in ("auto", "word_com"):
            pip_cmds.append([sys.executable, "-m", "pip", "install", "docx2pdf", "pywin32"])

        system_cmds: list[list[str]] = []
        if not python_only and engine in ("auto", "libreoffice"):
            if os.name == "nt":
                if shutil.which("winget"):
                    system_cmds.append(
                        ["winget", "install", "--accept-package-agreements", "TheDocumentFoundation.LibreOffice"],
                    )
                elif shutil.which("choco"):
                    system_cmds.append(["choco", "install", "libreoffice", "-y"])
            elif sys.platform.startswith("linux"):
                if shutil.which("apt"):
                    system_cmds.append(["sudo", "apt", "update"])
                    system_cmds.append(["sudo", "apt", "install", "-y", "libreoffice"])
                elif shutil.which("dnf"):
                    system_cmds.append(["sudo", "dnf", "install", "-y", "libreoffice"])
                elif shutil.which("pacman"):
                    system_cmds.append(["sudo", "pacman", "-S", "--noconfirm", "libreoffice-fresh"])
            elif sys.platform == "darwin" and shutil.which("brew"):
                system_cmds.append(["brew", "install", "--cask", "libreoffice"])

        all_cmds = pip_cmds + system_cmds

        if dry:
            self.stdout.write(self.style.WARNING("Modo dry-run: nenhum comando foi executado."))
            for c in all_cmds:
                self.stdout.write("  " + " ".join(c))
            return

        if not yes:
            self.stdout.write(
                self.style.WARNING("Nada executado. Reveja os comandos abaixo e rode novamente com --yes."),
            )
            for c in all_cmds:
                self.stdout.write("  " + " ".join(c))
            self.stdout.write("Comandos com sudo exigem privilégios de administrador no terminal.")
            return

        for c in all_cmds:
            self.stdout.write("Executando: " + " ".join(c))
            r = subprocess.run(c, check=False)
            if r.returncode != 0:
                self.stderr.write(self.style.ERROR(f"Comando falhou (código {r.returncode}): {' '.join(c)}"))
                return
        self.stdout.write(self.style.SUCCESS("Comandos concluídos. Rode: python manage.py documentos_check"))
