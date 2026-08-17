CREATE TABLE `apiKeys` (
	`id` int AUTO_INCREMENT NOT NULL,
	`userId` int NOT NULL,
	`name` varchar(80) NOT NULL,
	`keyPrefix` varchar(24) NOT NULL,
	`keyHash` varchar(64) NOT NULL,
	`state` enum('active','revoked') NOT NULL DEFAULT 'active',
	`lastUsedAt` timestamp,
	`revokedAt` timestamp,
	`createdAt` timestamp NOT NULL DEFAULT (now()),
	CONSTRAINT `apiKeys_id` PRIMARY KEY(`id`),
	CONSTRAINT `apiKeys_keyHash_unique` UNIQUE(`keyHash`)
);
--> statement-breakpoint
CREATE TABLE `apiUsageLogs` (
	`id` int AUTO_INCREMENT NOT NULL,
	`apiKeyId` int NOT NULL,
	`userId` int NOT NULL,
	`endpoint` varchar(120) NOT NULL,
	`statusCode` int NOT NULL,
	`createdAt` timestamp NOT NULL DEFAULT (now()),
	CONSTRAINT `apiUsageLogs_id` PRIMARY KEY(`id`)
);
--> statement-breakpoint
CREATE TABLE `trainingPairs` (
	`id` int AUTO_INCREMENT NOT NULL,
	`userId` int NOT NULL,
	`prompt` text NOT NULL,
	`response` text NOT NULL,
	`language` enum('ko','en','mixed') NOT NULL DEFAULT 'mixed',
	`source` enum('manual','local_suggestion') NOT NULL DEFAULT 'manual',
	`status` enum('draft','approved') NOT NULL DEFAULT 'approved',
	`createdAt` timestamp NOT NULL DEFAULT (now()),
	`updatedAt` timestamp NOT NULL DEFAULT (now()) ON UPDATE CURRENT_TIMESTAMP,
	CONSTRAINT `trainingPairs_id` PRIMARY KEY(`id`)
);
--> statement-breakpoint
CREATE TABLE `trainingRuns` (
	`id` int AUTO_INCREMENT NOT NULL,
	`userId` int NOT NULL,
	`status` enum('queued','running','completed','failed') NOT NULL DEFAULT 'queued',
	`requestedSteps` int NOT NULL,
	`currentStep` int NOT NULL DEFAULT 0,
	`progress` int NOT NULL DEFAULT 0,
	`loss` float,
	`note` text,
	`startedAt` timestamp,
	`completedAt` timestamp,
	`createdAt` timestamp NOT NULL DEFAULT (now()),
	CONSTRAINT `trainingRuns_id` PRIMARY KEY(`id`)
);
--> statement-breakpoint
CREATE INDEX `apiKeys_userId_idx` ON `apiKeys` (`userId`);--> statement-breakpoint
CREATE INDEX `apiUsageLogs_apiKeyId_idx` ON `apiUsageLogs` (`apiKeyId`);--> statement-breakpoint
CREATE INDEX `apiUsageLogs_userId_idx` ON `apiUsageLogs` (`userId`);--> statement-breakpoint
CREATE INDEX `trainingPairs_userId_idx` ON `trainingPairs` (`userId`);--> statement-breakpoint
CREATE INDEX `trainingRuns_userId_idx` ON `trainingRuns` (`userId`);