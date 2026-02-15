import { SimpleGrid, Spinner, Text } from "@chakra-ui/react";
import StatCard from "../../components/StatCard";
import StatusBadge from "../../components/StatusBadge";
import { useStatus } from "../../hooks/useStatus";

export default function StatusPanel() {
  const { data, isLoading, isError } = useStatus();

  if (isLoading) return <Spinner />;
  if (isError || !data) return <Text color="red.400">Failed to load status</Text>;

  const pnlColor = data.daily_pnl >= 0 ? "green.400" : "red.400";

  return (
    <SimpleGrid columns={{ base: 1, sm: 3 }} spacing={4}>
      <StatCard label="Bot Status" value="">
        <StatusBadge status={data.status} />
      </StatCard>
      <StatCard
        label="Total Assets"
        value={`${data.total_assets_usdc.toFixed(2)} USDC`}
      />
      <StatCard
        label="Daily PnL"
        value={`${data.daily_pnl >= 0 ? "+" : ""}${data.daily_pnl.toFixed(4)} USDC`}
        color={pnlColor}
      />
    </SimpleGrid>
  );
}
