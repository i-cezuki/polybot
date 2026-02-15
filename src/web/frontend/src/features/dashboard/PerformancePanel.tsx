import { Box, Heading, Spinner, Text, SimpleGrid } from "@chakra-ui/react";
import StatCard from "../../components/StatCard";
import { usePerformance } from "../../hooks/usePerformance";

export default function PerformancePanel() {
  const { data, isLoading, isError } = usePerformance();

  if (isLoading) return <Spinner />;
  if (isError) return <Text color="red.400">Failed to load performance</Text>;
  if (!data) return null;

  const pnlColor = data.total_pnl >= 0 ? "green.400" : "red.400";

  return (
    <Box bg="gray.800" borderRadius="lg" p={4}>
      <Heading size="sm" mb={3}>
        Performance ({data.period_days}d)
      </Heading>
      <SimpleGrid columns={1} spacing={3}>
        <StatCard
          label="Total PnL"
          value={`${data.total_pnl >= 0 ? "+" : ""}${data.total_pnl.toFixed(4)}`}
          color={pnlColor}
        />
        <StatCard label="Win Rate" value={`${data.win_rate.toFixed(1)}%`} />
        <StatCard label="Total Trades" value={data.total_trades} />
        <StatCard
          label="W / L"
          value={`${data.winning_trades} / ${data.losing_trades}`}
        />
      </SimpleGrid>
    </Box>
  );
}
