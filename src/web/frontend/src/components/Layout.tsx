import { Box, Flex, IconButton, Drawer, DrawerOverlay, DrawerContent, DrawerCloseButton, DrawerBody, useBreakpointValue } from "@chakra-ui/react";
import { Outlet } from "react-router-dom";
import { MdMenu } from "react-icons/md";
import Sidebar from "./Sidebar";
import { useUIStore } from "../store/uiStore";

export default function Layout() {
  const sidebarOpen = useUIStore((s) => s.sidebarOpen);
  const setSidebarOpen = useUIStore((s) => s.setSidebarOpen);
  const isMobile = useBreakpointValue({ base: true, md: false });

  return (
    <Flex minH="100vh">
      {isMobile ? (
        <>
          <IconButton
            aria-label="Open menu"
            icon={<MdMenu />}
            position="fixed"
            top={3}
            left={3}
            zIndex={20}
            onClick={() => setSidebarOpen(true)}
            size="sm"
          />
          <Drawer
            isOpen={sidebarOpen}
            placement="left"
            onClose={() => setSidebarOpen(false)}
          >
            <DrawerOverlay />
            <DrawerContent bg="gray.800" maxW="220px">
              <DrawerCloseButton />
              <DrawerBody p={0}>
                <Sidebar />
              </DrawerBody>
            </DrawerContent>
          </Drawer>
        </>
      ) : (
        <Sidebar />
      )}
      <Box flex={1} p={6} overflowY="auto">
        <Outlet />
      </Box>
    </Flex>
  );
}
