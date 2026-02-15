import { Box, Grid, GridItem } from "@chakra-ui/react";
import StatusPanel from "./StatusPanel";
import PositionsTable from "./PositionsTable";
import PerformancePanel from "./PerformancePanel";
import LogPanel from "./LogPanel";

export default function DashboardPage() {
  return (
    <Box>
      <StatusPanel />

      <Grid
        mt={4}
        templateColumns={{ base: "1fr", lg: "2fr 1fr" }}
        gap={4}
      >
        <GridItem>
          <PositionsTable />
        </GridItem>
        <GridItem>
          <PerformancePanel />
        </GridItem>
      </Grid>

      <Box mt={4}>
        <LogPanel />
      </Box>
    </Box>
  );
}
