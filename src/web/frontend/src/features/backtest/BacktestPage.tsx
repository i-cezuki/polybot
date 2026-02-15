import { Box, Heading, Text } from "@chakra-ui/react";
import BacktestForm from "./BacktestForm";
import BacktestResults from "./BacktestResults";
import { useBacktest } from "../../hooks/useBacktest";

export default function BacktestPage() {
  const mutation = useBacktest();

  return (
    <Box>
      <Heading size="md" mb={4}>
        Backtest
      </Heading>

      <BacktestForm
        onSubmit={(params) => mutation.mutate(params)}
        isLoading={mutation.isPending}
      />

      {mutation.isError && (
        <Text color="red.400" mt={4}>
          Error: {(mutation.error as Error).message}
        </Text>
      )}

      {mutation.isSuccess && mutation.data && (
        <BacktestResults data={mutation.data} />
      )}
    </Box>
  );
}
