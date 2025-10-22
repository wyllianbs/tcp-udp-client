#!/usr/bin/python3

'''
Cliente Socket Unificado: Suporta TCP ou UDP com POO e Type Hints

FUNCIONAMENTO:
==============
Este cliente permite conectar a um servidor socket usando protocolo TCP ou UDP.

1. ENTRADA DO USUÁRIO:
   - URL: Endereço do servidor (exemplo: localhost, 192.168.1.10, example.com)
     * Pode incluir protocolo: http://example.com ou tcp://example.com
     * Pode incluir porta: example.com:9000

   - Porta: Número da porta (1-65535, padrão: 8080)
     * Se especificada na URL, prevalece sobre entrada separada

   - Protocolo: TCP ou UDP (padrão: TCP)
     * TCP: Cria nova conexão para cada mensagem enviada
     * UDP: Mantém socket aberto durante toda a sessão

2. COMPORTAMENTO DO CLIENTE:
   - TCP: Conecta, envia mensagem, recebe resposta, desconecta (ciclo repetido)
   - UDP: Abre socket uma vez, envia/recebe múltiplas mensagens
   - Timeout: 2 minutos de inatividade encerra o cliente automaticamente
   - Loop interativo: Permite enviar múltiplas mensagens até digitar exit/quit

3. MENSAGENS SUPORTADAS:
   - ping     → Testa conectividade com servidor
   - time     → Solicita data/hora do servidor
   - help     → Lista comandos disponíveis no servidor
   - exit/quit → Encerra a sessão
   - Qualquer outro texto → Enviado ao servidor como mensagem

4. EXEMPLO DE USO:
   $ python3 TCP_UDP_client.py
   URL: localhost:8080
   Porta: [enter para usar da URL]
   Protocolo: TCP

   Mensagem: ping
   Resposta: Servidor: pong

5. DIFERENÇAS TCP vs UDP:
   TCP:
   - Estabelece conexão antes de enviar dados
   - Garante entrega e ordem das mensagens
   - Mais overhead, mas mais confiável
   - Nova conexão para cada mensagem (stateless)

   UDP:
   - Não estabelece conexão
   - Não garante entrega ou ordem
   - Menos overhead, mais rápido
   - Socket mantido aberto (stateful)

ARQUITETURA:
============
- Padrão Factory para criação de clientes
- Classe abstrata SocketClient define interface comum
- TCPClient e UDPClient implementam protocolos específicos
- URLParser processa e valida URLs
- TimeoutHandler gerencia timeout de inatividade
'''

import socket
import sys
import signal
import re
import urllib.parse
from typing import Tuple, Optional
from abc import ABC, abstractmethod
from enum import Enum


class Protocol(Enum):
    """Enumeração para protocolos disponíveis"""
    TCP = "TCP"
    UDP = "UDP"


class TimeoutHandler:
    """Gerenciador de timeout da aplicação"""

    def __init__(self, timeout: int = 120) -> None:
        self.timeout = timeout
        signal.signal(signal.SIGALRM, self._timeout_callback)

    def _timeout_callback(self, signum: int, frame) -> None:
        raise Exception(
            f"\n>>> Aplicação encerrada devido a inatividade: {self.timeout} segundos.\n")

    def start(self) -> None:
        """Inicia o timer de timeout"""
        signal.alarm(self.timeout)

    def stop(self) -> None:
        """Para o timer de timeout"""
        signal.alarm(0)

    def reset(self) -> None:
        """Reseta o timer de timeout"""
        signal.alarm(self.timeout)


class URLParser:
    """Classe para processar e extrair informações de URLs"""

    @staticmethod
    def extract_host_port(url: str, default_port: int) -> Tuple[str, int]:
        """
        Extrai host e porta da URL fornecida

        Args:
            url: URL a ser processada
            default_port: Porta padrão caso não seja especificada

        Returns:
            Tupla contendo (host, port)
        """
        if not re.match(r'^[a-zA-Z]+://', url):
            url = 'http://' + url

        parsed_url = urllib.parse.urlparse(url)
        host = parsed_url.netloc

        if ':' in host:
            host, port_str = host.split(':')
            port = int(port_str)
        else:
            port = default_port

        return host, port


class SocketClient(ABC):
    """Classe abstrata base para clientes de socket"""

    BUFFER_SIZE: int = 1024

    def __init__(self, host: str, port: int, timeout_handler: TimeoutHandler) -> None:
        self.host = host
        self.port = port
        self.timeout_handler = timeout_handler
        self.socket: Optional[socket.socket] = None

    @abstractmethod
    def connect(self) -> None:
        """Estabelece conexão com o servidor"""
        pass

    @abstractmethod
    def send_message(self, message: str) -> None:
        """Envia mensagem ao servidor"""
        pass

    @abstractmethod
    def receive_message(self) -> str:
        """Recebe mensagem do servidor"""
        pass

    @abstractmethod
    def close(self) -> None:
        """Fecha a conexão"""
        pass

    def run(self) -> None:
        """Loop principal de execução do cliente"""
        print(f"\n=== Modo {self.__class__.__name__.replace('Client', '')} ===")
        print(f"Servidor: {self.host}:{self.port}\n")

        try:
            self.timeout_handler.start()
            self._message_loop()
            self.timeout_handler.stop()
        except Exception as e:
            print(e)
            sys.exit()

    def _message_loop(self) -> None:
        """Loop de envio e recebimento de mensagens"""
        while True:
            try:
                msg = input('Mensagem para enviar (exit/quit para sair): ')

                self._handle_message(msg)

                if msg.lower() in ['exit', 'quit']:
                    print("Conexão encerrada.")
                    break

            except socket.error as e:
                print(f"Erro de socket: {e}")
                break

    @abstractmethod
    def _handle_message(self, message: str) -> None:
        """Processa envio e recebimento de mensagem"""
        pass


class TCPClient(SocketClient):
    """Cliente TCP que cria nova conexão para cada mensagem"""

    def connect(self) -> None:
        """Cria um novo socket TCP e conecta ao servidor"""
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect((self.host, self.port))
        print(f"✓ Conectado ao servidor {self.host}:{self.port}")

    def send_message(self, message: str) -> None:
        """Envia mensagem via TCP"""
        if self.socket:
            self.socket.sendall(message.encode('utf-8'))

    def receive_message(self) -> str:
        """Recebe mensagem via TCP"""
        if self.socket:
            data = self.socket.recv(self.BUFFER_SIZE)
            return data.decode('utf-8')
        return ""

    def close(self) -> None:
        """Fecha o socket TCP"""
        if self.socket:
            self.socket.close()

    def _handle_message(self, message: str) -> None:
        """Processa mensagem TCP com nova conexão para cada envio"""
        try:
            self.connect()

            if message.lower() in ['exit', 'quit']:
                print("Enviando comando para encerrar conexão...")

            self.send_message(message)
            response = self.receive_message()
            print(f"Resposta do servidor: {response}\n")

        finally:
            self.close()


class UDPClient(SocketClient):
    """Cliente UDP que mantém socket aberto"""

    def __init__(self, host: str, port: int, timeout_handler: TimeoutHandler) -> None:
        super().__init__(host, port, timeout_handler)
        self.connect()

    def connect(self) -> None:
        """Cria socket UDP"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            print(f"✓ Socket UDP criado para {self.host}:{self.port}")
        except socket.error:
            print("Falha ao criar socket UDP")
            sys.exit()

    def send_message(self, message: str) -> None:
        """Envia mensagem via UDP"""
        if self.socket:
            self.socket.sendto(message.encode('utf-8'), (self.host, self.port))

    def receive_message(self) -> str:
        """Recebe mensagem via UDP"""
        if self.socket:
            data, addr = self.socket.recvfrom(self.BUFFER_SIZE)
            return data.decode('utf-8')
        return ""

    def close(self) -> None:
        """Fecha o socket UDP"""
        if self.socket:
            self.socket.close()

    def _handle_message(self, message: str) -> None:
        """Processa mensagem UDP"""
        self.send_message(message)
        response = self.receive_message()
        print(f"Resposta do servidor: {response}\n")


class ClientFactory:
    """Factory para criar clientes apropriados"""

    @staticmethod
    def create_client(
        protocol: Protocol,
        host: str,
        port: int,
        timeout_handler: TimeoutHandler
    ) -> SocketClient:
        """
        Cria instância do cliente apropriado

        Args:
            protocol: Protocolo a ser utilizado (TCP ou UDP)
            host: Endereço do servidor
            port: Porta do servidor
            timeout_handler: Gerenciador de timeout

        Returns:
            Instância de SocketClient (TCPClient ou UDPClient)
        """
        if protocol == Protocol.TCP:
            return TCPClient(host, port, timeout_handler)
        elif protocol == Protocol.UDP:
            return UDPClient(host, port, timeout_handler)
        else:
            raise ValueError(f"Protocolo inválido: {protocol}")


class ClientApplication:
    """Aplicação principal do cliente"""

    def __init__(self) -> None:
        self.timeout_handler = TimeoutHandler(timeout=120)

    def _get_user_input(self) -> Tuple[str, int, Protocol]:
        """
        Solicita informações do usuário

        Returns:
            Tupla contendo (host, port, protocol)
        """
        print("=" * 50)
        print("    Cliente Socket Unificado (TCP/UDP)")
        print("=" * 50)

        # URL
        url_input = input('URL do servidor [Padrão: example.com]: ').strip()
        if not url_input:
            url_input = 'example.com'

        # Porta
        port_input = input('Porta do servidor [Padrão: 8080]: ').strip()
        if not port_input:
            port = 8080
        else:
            try:
                port = int(port_input)
            except ValueError:
                print("Porta inválida! Usando porta padrão 8080")
                port = 8080

        # Extrair host
        host, port = URLParser.extract_host_port(url_input, port)

        # Protocolo
        while True:
            protocol_input = input('Protocolo (TCP/UDP) [Padrão: TCP]: ').strip().upper()
            if not protocol_input:
                protocol_input = 'TCP'

            try:
                protocol = Protocol(protocol_input)
                break
            except ValueError:
                print("Protocolo inválido! Use TCP ou UDP.")

        return host, port, protocol

    def run(self) -> None:
        """Executa a aplicação"""
        host, port, protocol = self._get_user_input()

        client = ClientFactory.create_client(
            protocol=protocol,
            host=host,
            port=port,
            timeout_handler=self.timeout_handler
        )

        client.run()
        sys.exit(0)


def main() -> None:
    """Função principal"""
    app = ClientApplication()
    app.run()


if __name__ == '__main__':
    main()
