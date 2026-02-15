import {
  Box,
  Flex,
  Heading,
  VStack,
  Switch,
  Text,
  HStack,
} from "@chakra-ui/react";
import { NavLink } from "react-router-dom";
import { MdDashboard, MdShowChart } from "react-icons/md";
import { useUIStore } from "../store/uiStore";

const navItems = [
  { to: "/", label: "Dashboard", icon: MdDashboard },
  { to: "/backtest", label: "Backtest", icon: MdShowChart },
];

export default function Sidebar() {
  const pollingEnabled = useUIStore((s) => s.pollingEnabled);
  const togglePolling = useUIStore((s) => s.togglePolling);

  return (
    <Box
      w="220px"
      bg="gray.800"
      minH="100vh"
      py={6}
      px={4}
      display="flex"
      flexDirection="column"
    >
      <Heading size="md" mb={8} px={2}>
        PolyBot
      </Heading>

      <VStack spacing={1} align="stretch" flex={1}>
        {navItems.map(({ to, label, icon: Icon }) => (
          <NavLink key={to} to={to} end>
            {({ isActive }) => (
              <Flex
                align="center"
                gap={3}
                px={3}
                py={2}
                borderRadius="md"
                bg={isActive ? "whiteAlpha.200" : "transparent"}
                _hover={{ bg: "whiteAlpha.100" }}
                fontWeight={isActive ? "bold" : "normal"}
              >
                <Icon />
                <Text fontSize="sm">{label}</Text>
              </Flex>
            )}
          </NavLink>
        ))}
      </VStack>

      <HStack px={2} spacing={2}>
        <Text fontSize="xs" color="gray.400">
          Polling
        </Text>
        <Switch
          size="sm"
          isChecked={pollingEnabled}
          onChange={togglePolling}
          colorScheme="green"
        />
      </HStack>
    </Box>
  );
}
