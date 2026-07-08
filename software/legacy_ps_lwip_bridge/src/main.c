#include <stdint.h>

#include "lwip/dhcp.h"
#include "lwip/tcp.h"
#include "netif/xadapter.h"
#include "platform.h"
#include "platform_config.h"
#include "xil_printf.h"
#include "xstatus.h"

#include "ir_hw.h"
#include "tcp_bridge.h"

#define RF_TCP_PORT 5001u
#define DHCP_WAIT_ITERATIONS 24

extern volatile int TcpFastTmrFlag;
extern volatile int TcpSlowTmrFlag;
extern volatile int dhcp_timoutcntr;

void lwip_init(void);
void tcp_fasttmr(void);
void tcp_slowtmr(void);

static struct netif server_netif;
static ir_hw_t ir_hw;
struct netif *echo_netif = &server_netif;

static void print_ip(const char *msg, const ip_addr_t *ip)
{
	xil_printf("%s%d.%d.%d.%d\r\n", msg,
	           ip4_addr1(ip), ip4_addr2(ip),
	           ip4_addr3(ip), ip4_addr4(ip));
}

static void print_ip_settings(const ip_addr_t *ip,
                              const ip_addr_t *mask,
                              const ip_addr_t *gw)
{
	print_ip("Board IP: ", ip);
	print_ip("Netmask : ", mask);
	print_ip("Gateway : ", gw);
}

static void set_static_fallback(struct netif *netif)
{
	IP4_ADDR(&(netif->ip_addr), 192, 168, 10, 2);
	IP4_ADDR(&(netif->netmask), 255, 255, 255, 0);
	IP4_ADDR(&(netif->gw), 192, 168, 10, 1);
}

int main(void)
{
	ip_addr_t ipaddr;
	ip_addr_t netmask;
	ip_addr_t gw;
	unsigned char mac_ethernet_address[] = {
		0x00, 0x0a, 0x35, 0x00, 0x01, 0x10
	};

	xil_printf("\r\nRF_COMM PS lwIP bridge\r\n");
	init_platform();

	ipaddr.addr = 0u;
	netmask.addr = 0u;
	gw.addr = 0u;

	lwip_init();
	if (!xemac_add(&server_netif, &ipaddr, &netmask, &gw,
	               mac_ethernet_address, PLATFORM_EMAC_BASEADDR)) {
		xil_printf("Error adding network interface\r\n");
		return -1;
	}

	netif_set_default(&server_netif);
	netif_set_up(&server_netif);
	platform_enable_interrupts();

#if LWIP_DHCP
	dhcp_start(&server_netif);
	dhcp_timoutcntr = DHCP_WAIT_ITERATIONS;
	while ((server_netif.ip_addr.addr == 0u) && (dhcp_timoutcntr > 0)) {
		xemacif_input(&server_netif);
	}
	if (server_netif.ip_addr.addr == 0u) {
		xil_printf("DHCP timeout, using static fallback\r\n");
		set_static_fallback(&server_netif);
	}
#else
	set_static_fallback(&server_netif);
#endif

	ipaddr.addr = server_netif.ip_addr.addr;
	netmask.addr = server_netif.netmask.addr;
	gw.addr = server_netif.gw.addr;
	print_ip_settings(&ipaddr, &netmask, &gw);

	if (ir_hw_init(&ir_hw) != XST_SUCCESS) {
		xil_printf("IR hardware init failed\r\n");
		return -1;
	}

	if (tcp_bridge_start(&ir_hw, RF_TCP_PORT) != XST_SUCCESS) {
		xil_printf("TCP bridge start failed\r\n");
		return -1;
	}

	while (1) {
		if (TcpFastTmrFlag) {
			tcp_fasttmr();
			TcpFastTmrFlag = 0;
		}
		if (TcpSlowTmrFlag) {
			tcp_slowtmr();
			TcpSlowTmrFlag = 0;
		}

		xemacif_input(&server_netif);
		tcp_bridge_poll();
	}
}
