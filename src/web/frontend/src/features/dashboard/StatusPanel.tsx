import {
  SimpleGrid,
  Spinner,
  Text,
  Flex,
  HStack,
  Switch,
  Badge,
  Button,
  IconButton,
  useDisclosure,
  useToast,
  Box,
} from "@chakra-ui/react";
import { MdWarning, MdNotifications } from "react-icons/md";
import StatCard from "../../components/StatCard";
import StatusBadge from "../../components/StatusBadge";
import PanicConfirmModal from "../../components/PanicConfirmModal";
import { useStatus } from "../../hooks/useStatus";
import { useDryRunToggle } from "../../hooks/useDryRunToggle";
import { usePanicClose } from "../../hooks/usePanicClose";
import { useTestNotification } from "../../hooks/useTestNotification";
import { useUIStore } from "../../store/uiStore";

export default function StatusPanel() {
  const { data, isLoading, isError } = useStatus();
  const dryRunToggle = useDryRunToggle();
  const panicClose = usePanicClose();
  const testNotif = useTestNotification();
  const dryRunOverride = useUIStore((s) => s.dryRunOverride);
  const { isOpen, onOpen, onClose } = useDisclosure();
  const toast = useToast();

  if (isLoading) return <Spinner />;
  if (isError || !data) return <Text color="red.400">Failed to load status</Text>;

  const isDryRun = dryRunOverride ?? data.dry_run;
  const pnlColor = data.daily_pnl >= 0 ? "green.400" : "red.400";

  const handleDryRunToggle = () => {
    dryRunToggle.mutate(
      { enabled: !isDryRun },
      {
        onError: () => {
          toast({ title: "Failed to toggle dry-run mode", status: "error", duration: 3000 });
        },
      }
    );
  };

  const handlePanicConfirm = () => {
    panicClose.mutate(undefined, {
      onSuccess: (res) => {
        toast({
          title: "Panic close executed",
          description: `${res.closed_positions} position(s) closed`,
          status: "warning",
          duration: 5000,
        });
        onClose();
      },
      onError: () => {
        toast({ title: "Panic close failed", status: "error", duration: 3000 });
      },
    });
  };

  const handleTestNotification = () => {
    testNotif.mutate(undefined, {
      onSuccess: () => {
        toast({ title: "Test notification sent", status: "success", duration: 3000 });
      },
      onError: () => {
        toast({ title: "Failed to send test notification", status: "error", duration: 3000 });
      },
    });
  };

  return (
    <Box>
      <SimpleGrid columns={{ base: 1, sm: 3 }} spacing={4}>
        <StatCard label="Bot Status" value="">
          <HStack spacing={2}>
            <StatusBadge status={data.status} />
            <IconButton
              aria-label="Test notification"
              icon={<MdNotifications />}
              size="xs"
              variant="ghost"
              onClick={handleTestNotification}
              isLoading={testNotif.isPending}
            />
          </HStack>
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

      <Flex
        mt={4}
        p={4}
        bg="gray.800"
        borderRadius="lg"
        borderWidth={2}
        borderColor={isDryRun ? "gray.600" : "orange.400"}
        align="center"
        justify="space-between"
        wrap="wrap"
        gap={3}
      >
        <HStack spacing={3}>
          <Switch
            isChecked={isDryRun}
            onChange={handleDryRunToggle}
            colorScheme="green"
            isDisabled={dryRunToggle.isPending}
          />
          <Badge colorScheme={isDryRun ? "green" : "red"} fontSize="sm" px={2} py={1}>
            {isDryRun ? "DRY RUN" : "LIVE"}
          </Badge>
          {!isDryRun && (
            <Text color="orange.300" fontSize="sm">
              Live trading active
            </Text>
          )}
        </HStack>

        <Button
          colorScheme="red"
          leftIcon={<MdWarning />}
          onClick={onOpen}
          size="sm"
        >
          PANIC CLOSE
        </Button>
      </Flex>

      <PanicConfirmModal
        isOpen={isOpen}
        onClose={onClose}
        onConfirm={handlePanicConfirm}
        isLoading={panicClose.isPending}
      />
    </Box>
  );
}
