from django import forms

from .models import Viatura


class ServidorEquipeSelectMultiple(forms.SelectMultiple):
    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex=subindex, attrs=attrs)
        servidor = getattr(value, "instance", None)
        if servidor is None:
            return option

        cargo = servidor.cargo.nome if servidor.cargo_id and servidor.cargo else ""
        unidade = str(servidor.unidade) if servidor.unidade_id and servidor.unidade else ""
        rg = servidor.rg_formatado or ""
        cpf = servidor.cpf_formatado or ""
        main_parts = [
            servidor.nome,
            f"RG {rg}" if rg else "",
            f"CPF {cpf}" if cpf else "",
            cargo,
        ]
        main = " * ".join(part for part in main_parts if part)
        search = " ".join(part for part in [servidor.nome, rg, cpf, cargo, unidade] if part)
        unidade_id = str(servidor.unidade_id) if servidor.unidade_id else ""
        option["attrs"].update(
            {
                "data-cargo": cargo,
                "data-cpf": cpf,
                "data-main": main,
                "data-meta": unidade,
                "data-rg": rg,
                "data-search": search,
                "data-unidade": unidade,
                "data-unidade-id": unidade_id,
            },
        )
        return option


class ViaturaSelectSingle(forms.Select):
    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex=subindex, attrs=attrs)
        viatura = getattr(value, "instance", None)
        if viatura is None:
            return option

        placa = viatura.placa_formatada
        modelo = viatura.modelo or ""
        combustivel = str(viatura.combustivel) if viatura.combustivel_id and viatura.combustivel else ""
        tipo_display = dict(Viatura.TIPO_CHOICES).get(viatura.tipo, "") if viatura.tipo else ""
        unidade = str(viatura.unidade) if viatura.unidade_id and viatura.unidade else ""

        motorista_ids = ",".join(str(m.pk) for m in viatura.motoristas.all())
        unidade_id = str(viatura.unidade_id) if viatura.unidade_id else ""
        meta_parts = [p for p in [modelo, combustivel, tipo_display, unidade] if p]
        linha2_parts = [p for p in [combustivel, tipo_display, unidade] if p]
        search = " ".join(p for p in [viatura.placa, placa.replace("-", ""), modelo, combustivel, tipo_display, unidade] if p)

        option["label"] = " - ".join(p for p in [placa, modelo] if p)
        option["attrs"].update(
            {
                "data-main": placa,
                "data-meta": " - ".join(meta_parts),
                "data-cargo": " - ".join(linha2_parts),
                "data-motorista-ids": motorista_ids,
                "data-unidade-id": unidade_id,
                "data-search": search,
            },
        )
        return option


class CidadeSelectMultiple(forms.SelectMultiple):
    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex=subindex, attrs=attrs)
        cidade = getattr(value, "instance", None)
        if cidade is None:
            return option
        uf = cidade.uf or ""
        estado_nome = str(cidade.estado) if cidade.estado_id and cidade.estado else uf
        main = f"{cidade.nome}/{uf}" if uf else cidade.nome
        option["label"] = main
        option["attrs"].update({
            "data-main": main,
            "data-meta": estado_nome,
            "data-search": f"{cidade.nome} {uf} {estado_nome}",
            "data-uf": uf,
        })
        return option


class ServidorMotoristaSelect(forms.Select):
    """Select simples com metadados nos options para o picker de busca."""

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex=subindex, attrs=attrs)
        servidor = getattr(value, "instance", None)
        if servidor is None:
            return option

        cargo = servidor.cargo.nome if servidor.cargo_id and servidor.cargo else ""
        unidade = str(servidor.unidade) if servidor.unidade_id and servidor.unidade else ""
        rg = servidor.rg_formatado or ""
        cpf = servidor.cpf_formatado or ""
        main_parts = [
            servidor.nome,
            f"RG {rg}" if rg else "",
            f"CPF {cpf}" if cpf else "",
            cargo,
        ]
        main = " * ".join(part for part in main_parts if part)
        search = " ".join(part for part in [servidor.nome, rg, cpf, cargo, unidade] if part)
        unidade_id = str(servidor.unidade_id) if servidor.unidade_id else ""
        option["attrs"].update(
            {
                "data-cargo": cargo,
                "data-cpf": cpf,
                "data-main": main,
                "data-meta": unidade,
                "data-rg": rg,
                "data-search": search,
                "data-unidade": unidade,
                "data-unidade-id": unidade_id,
            },
        )
        return option
