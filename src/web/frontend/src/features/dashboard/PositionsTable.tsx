import {
  Box,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  Text,
  Spinner,
  Badge,
  Heading,
} from "@chakra-ui/react";
import { usePositions } from "../../hooks/usePositions";

export default function PositionsTable() {
  const { data, isLoading, isError } = usePositions();

  if (isLoading) return <Spinner />;
  if (isError) return <Text color="red.400">Failed to load positions</Text>;

  const positions = data?.positions ?? [];

  return (
    <Box bg="gray.800" borderRadius="lg" p={4} overflowX="auto">
      <Heading size="sm" mb={3}>
        Active Positions
      </Heading>
      {positions.length === 0 ? (
        <Text color="gray.500" fontSize="sm">
          No active positions
        </Text>
      ) : (
        <Table size="sm" variant="simple">
          <Thead>
            <Tr>
              <Th color="gray.400">Market</Th>
              <Th color="gray.400">Side</Th>
              <Th color="gray.400" isNumeric>Size (USDC)</Th>
              <Th color="gray.400" isNumeric>Avg Price</Th>
              <Th color="gray.400" isNumeric>PnL</Th>
              <Th color="gray.400">Opened</Th>
            </Tr>
          </Thead>
          <Tbody>
            {positions.map((p) => (
              <Tr key={p.asset_id}>
                <Td fontSize="xs">{p.market?.slice(0, 10) ?? p.asset_id}</Td>
                <Td>
                  <Badge colorScheme={p.side === "BUY" ? "green" : "red"} fontSize="xs">
                    {p.side}
                  </Badge>
                </Td>
                <Td isNumeric>{p.size_usdc.toFixed(2)}</Td>
                <Td isNumeric>{p.average_price.toFixed(4)}</Td>
                <Td
                  isNumeric
                  color={p.realized_pnl >= 0 ? "green.400" : "red.400"}
                >
                  {p.realized_pnl.toFixed(4)}
                </Td>
                <Td fontSize="xs">
                  {p.opened_at
                    ? new Date(p.opened_at).toLocaleString()
                    : "-"}
                </Td>
              </Tr>
            ))}
          </Tbody>
        </Table>
      )}
    </Box>
  );
}
