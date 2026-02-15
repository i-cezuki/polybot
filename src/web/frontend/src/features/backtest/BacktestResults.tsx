import {
  Box,
  SimpleGrid,
  Heading,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  Badge,
  Text,
} from "@chakra-ui/react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import StatCard from "../../components/StatCard";
import type { BacktestResponse } from "../../types/api";

interface BacktestResultsProps {
  data: BacktestResponse;
}

export default function BacktestResults({ data }: BacktestResultsProps) {
  if (data.error) {
    return (
      <Box bg="gray.800" borderRadius="lg" p={4} mt={4}>
        <Text color="red.400">{data.error}</Text>
      </Box>
    );
  }

  const a = data.analysis;
  const returnColor = a.total_return_pct >= 0 ? "green.400" : "red.400";

  return (
    <Box mt={4}>
      <Heading size="sm" mb={3}>
        Results
      </Heading>

      <SimpleGrid columns={{ base: 2, md: 3, lg: 6 }} spacing={3} mb={4}>
        <StatCard label="Initial Capital" value={`${a.initial_capital.toFixed(2)}`} />
        <StatCard label="Final Capital" value={`${a.final_capital.toFixed(2)}`} />
        <StatCard
          label="Total PnL"
          value={`${a.total_pnl >= 0 ? "+" : ""}${a.total_pnl.toFixed(2)}`}
          color={returnColor}
        />
        <StatCard
          label="Return"
          value={`${a.total_return_pct.toFixed(2)}%`}
          color={returnColor}
        />
        <StatCard label="Win Rate" value={`${a.win_rate_pct.toFixed(1)}%`} />
        <StatCard label="Sharpe" value={a.sharpe_ratio.toFixed(2)} />
      </SimpleGrid>

      <SimpleGrid columns={{ base: 1, md: 2 }} spacing={3} mb={4}>
        <StatCard label="Max Drawdown" value={`${a.max_drawdown_pct.toFixed(2)}%`} color="red.400" />
        <StatCard label="Total Trades" value={a.total_trades} />
      </SimpleGrid>

      {data.equity_curve.length > 0 && (
        <Box bg="gray.800" borderRadius="lg" p={4} mb={4}>
          <Heading size="xs" mb={3}>
            Equity Curve
          </Heading>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={data.equity_curve}>
              <CartesianGrid strokeDasharray="3 3" stroke="#444" />
              <XAxis
                dataKey="timestamp"
                tick={{ fontSize: 10, fill: "#aaa" }}
                tickFormatter={(v: string) => v.slice(11, 16)}
              />
              <YAxis tick={{ fontSize: 10, fill: "#aaa" }} />
              <Tooltip
                contentStyle={{
                  backgroundColor: "#1a1a2e",
                  border: "1px solid #444",
                  borderRadius: "6px",
                  fontSize: "12px",
                }}
              />
              <Line
                type="monotone"
                dataKey="equity"
                stroke="#63b3ed"
                dot={false}
                strokeWidth={2}
              />
            </LineChart>
          </ResponsiveContainer>
        </Box>
      )}

      {data.trades.length > 0 && (
        <Box bg="gray.800" borderRadius="lg" p={4} overflowX="auto">
          <Heading size="xs" mb={3}>
            Trades ({data.trades.length})
          </Heading>
          <Table size="sm" variant="simple">
            <Thead>
              <Tr>
                <Th color="gray.400">Action</Th>
                <Th color="gray.400" isNumeric>Price</Th>
                <Th color="gray.400" isNumeric>Amount (USDC)</Th>
                <Th color="gray.400" isNumeric>PnL</Th>
                <Th color="gray.400">Reason</Th>
              </Tr>
            </Thead>
            <Tbody>
              {data.trades.map((t, i) => (
                <Tr key={i}>
                  <Td>
                    <Badge
                      colorScheme={t.action === "BUY" ? "green" : "red"}
                      fontSize="xs"
                    >
                      {t.action}
                    </Badge>
                  </Td>
                  <Td isNumeric>{t.price.toFixed(4)}</Td>
                  <Td isNumeric>{t.amount_usdc.toFixed(2)}</Td>
                  <Td
                    isNumeric
                    color={t.realized_pnl >= 0 ? "green.400" : "red.400"}
                  >
                    {t.realized_pnl.toFixed(4)}
                  </Td>
                  <Td fontSize="xs" maxW="200px" isTruncated>
                    {t.reason ?? "-"}
                  </Td>
                </Tr>
              ))}
            </Tbody>
          </Table>
        </Box>
      )}
    </Box>
  );
}
