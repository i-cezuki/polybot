import { useState } from "react";
import {
  Box,
  Button,
  FormControl,
  FormLabel,
  Input,
  NumberInput,
  NumberInputField,
  NumberInputStepper,
  NumberIncrementStepper,
  NumberDecrementStepper,
  VStack,
  Heading,
} from "@chakra-ui/react";
import type { BacktestParams } from "../../types/api";

interface BacktestFormProps {
  onSubmit: (params: BacktestParams) => void;
  isLoading: boolean;
}

export default function BacktestForm({ onSubmit, isLoading }: BacktestFormProps) {
  const [days, setDays] = useState(7);
  const [marketId, setMarketId] = useState("");
  const [initialCapital, setInitialCapital] = useState(10000);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit({
      days,
      market_id: marketId || undefined,
      initial_capital: initialCapital,
    });
  };

  return (
    <Box bg="gray.800" borderRadius="lg" p={6}>
      <Heading size="sm" mb={4}>
        Backtest Configuration
      </Heading>
      <form onSubmit={handleSubmit}>
        <VStack spacing={4} align="stretch">
          <FormControl>
            <FormLabel fontSize="sm">Period (days)</FormLabel>
            <NumberInput
              value={days}
              onChange={(_, v) => setDays(v || 7)}
              min={1}
              max={90}
              size="sm"
            >
              <NumberInputField />
              <NumberInputStepper>
                <NumberIncrementStepper />
                <NumberDecrementStepper />
              </NumberInputStepper>
            </NumberInput>
          </FormControl>

          <FormControl>
            <FormLabel fontSize="sm">Market ID (optional)</FormLabel>
            <Input
              value={marketId}
              onChange={(e) => setMarketId(e.target.value)}
              placeholder="e.g. 0xabc..."
              size="sm"
            />
          </FormControl>

          <FormControl>
            <FormLabel fontSize="sm">Initial Capital (USDC)</FormLabel>
            <NumberInput
              value={initialCapital}
              onChange={(_, v) => setInitialCapital(v || 10000)}
              min={100}
              size="sm"
            >
              <NumberInputField />
              <NumberInputStepper>
                <NumberIncrementStepper />
                <NumberDecrementStepper />
              </NumberInputStepper>
            </NumberInput>
          </FormControl>

          <Button
            type="submit"
            colorScheme="blue"
            isLoading={isLoading}
            loadingText="Running..."
            size="sm"
          >
            Execute Backtest
          </Button>
        </VStack>
      </form>
    </Box>
  );
}
